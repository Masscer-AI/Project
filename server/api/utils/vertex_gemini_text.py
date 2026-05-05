"""
Vertex AI Gemini text generation via the ``google-genai`` SDK (same stack as
:mod:`api.ai_layers.tools.create_image`).

Environment variables
---------------------

**Required for Vertex (typical)**

- ``GOOGLE_CLOUD_PROJECT`` — GCP project id (defaults in some environments may exist; set explicitly in production).

**Text Gemini region**

- ``VERTEX_TEXT_LOCATION`` — defaults to ``global`` (matches Agent Platform / ``gemini-3.1-flash-lite-preview`` docs).
  Image generation uses ``GOOGLE_CLOUD_LOCATION`` (often ``us-central1``); text uses this separate variable so preview models on the global endpoint do not pick up the wrong region.

**Authentication (one of)**

- Application Default Credentials (recommended on GCP / GKE / Cloud Run).
- ``GOOGLE_APPLICATION_CREDENTIALS`` — path to a service account JSON file.
- ``GOOGLE_APPLICATION_CREDENTIALS_JSON`` — raw JSON string; a temp file is written and pointed to by ``GOOGLE_APPLICATION_CREDENTIALS`` (same pattern as image generation).

Integration status
-------------------

:class:`VertexGeminiText` powers single-turn :meth:`~VertexGeminiText.infer` and
:class:`~api.ai_layers.vertex_gemini_agent_loop.VertexGeminiAgentLoop` for chat
agents whose :class:`~api.ai_layers.models.LanguageModel` is under the **Google**
provider. Wire-up uses ``agent.llm`` / provider name ``google`` — see
``conversation_agent_task``.
"""

from __future__ import annotations

import json as json_lib
import os
import tempfile
from dataclasses import dataclass
from typing import Any

DEFAULT_VERTEX_TEXT_MODEL = "gemini-3.1-flash-lite-preview"


def _setup_google_credentials() -> str | None:
    """
    Write GOOGLE_APPLICATION_CREDENTIALS_JSON to a temp file when needed.
    Returns temp path for cleanup, or an existing file path, or None if unset.
    """
    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip().strip("'\"")
    if not credentials_json:
        return None

    if os.path.isfile(credentials_json):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_json
        return credentials_json

    try:
        json_lib.loads(credentials_json)
    except json_lib.JSONDecodeError as exc:
        raise ValueError(f"GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON: {exc}") from exc

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, prefix="gcp_creds_")
    tmp.write(credentials_json)
    tmp.close()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
    return tmp.name


def _cleanup_temp_credentials(path: str | None) -> None:
    if not path:
        return
    if path.startswith(tempfile.gettempdir()) and path.endswith(".json"):
        try:
            os.unlink(path)
        except OSError:
            pass


def _openai_style_messages_to_contents(
    messages: list[dict[str, Any]],
    *,
    genai_types: Any,
) -> list[Any]:
    """Map [{"role":"user"|"assistant","content": str}] to Gemini Content list."""
    contents: list[Any] = []
    for m in messages:
        role = (m.get("role") or "").strip().lower()
        text = m.get("content")
        if not isinstance(text, str):
            text = str(text) if text is not None else ""
        text = text.strip()
        if not text:
            continue
        if role in ("assistant", "model"):
            gemini_role = "model"
        elif role == "user":
            gemini_role = "user"
        else:
            raise ValueError(f"Unsupported message role for Gemini: {role!r}")
        contents.append(
            genai_types.Content(
                role=gemini_role,
                parts=[genai_types.Part.from_text(text=text)],
            )
        )
    if not contents:
        raise ValueError("messages produced no non-empty user/model turns")
    return contents


def _extract_text_from_response(response: Any) -> str:
    """Concatenate text parts from the first candidate."""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return ""
    content = getattr(candidates[0], "content", None)
    if not content:
        return ""
    parts = getattr(content, "parts", None) or []
    chunks: list[str] = []
    for p in parts:
        t = getattr(p, "text", None)
        if t:
            chunks.append(t)
    return "".join(chunks).strip()


def _usage_to_dict(usage_metadata: Any) -> dict[str, int]:
    """
    Map Vertex usage_metadata to a simple dict.

    When ``response_token_count`` is missing/0 but ``total_token_count`` is set,
    completion tokens are approximated as ``total - prompt`` (not billing-grade).
    """
    if usage_metadata is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    pt = int(getattr(usage_metadata, "prompt_token_count", 0) or 0)
    ct = int(getattr(usage_metadata, "response_token_count", 0) or 0)
    tt = int(getattr(usage_metadata, "total_token_count", 0) or 0)
    # Vertex sometimes omits response_token_count; approximate from total − prompt when possible.
    if ct == 0 and tt > 0 and pt >= 0:
        approx = tt - pt
        if approx >= 0:
            ct = approx
    return {
        "prompt_tokens": pt,
        "completion_tokens": ct,
        "total_tokens": tt,
    }


@dataclass
class VertexGeminiInferResult:
    """Result of a single :meth:`VertexGeminiText.infer` call."""

    text: str
    usage: dict[str, int]
    model: str
    raw_response: Any | None = None


class VertexGeminiText:
    """
    Thin Vertex (Gemini) text client using ``google-genai``.

    Not thread-safe: create one instance per request/task if you use
    credential temp files.
    """

    def __init__(
        self,
        *,
        project: str | None = None,
        location: str | None = None,
    ) -> None:
        self.project = (project or os.environ.get("GOOGLE_CLOUD_PROJECT") or "").strip()
        if not self.project:
            raise ValueError(
                "GOOGLE_CLOUD_PROJECT is not set and no project was passed to VertexGeminiText()"
            )
        self.location = (
            location or os.environ.get("VERTEX_TEXT_LOCATION") or "global"
        ).strip()
        self._tmp_creds_path = _setup_google_credentials()
        self._client = None

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                from google import genai
            except ImportError as exc:
                raise ImportError(
                    "google-genai is required. Install dependencies from server/pyproject.toml"
                ) from exc
            self._client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
            )
        return self._client

    def close(self) -> None:
        """Remove temporary credential file if one was created."""
        _cleanup_temp_credentials(self._tmp_creds_path)
        self._tmp_creds_path = None
        self._client = None

    def __enter__(self) -> VertexGeminiText:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def infer(
        self,
        *,
        prompt: str | None = None,
        messages: list[dict[str, Any]] | None = None,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        include_raw_response: bool = False,
    ) -> VertexGeminiInferResult:
        """
        Run a single ``generate_content`` call.

        Provide either ``prompt`` (single user turn) or ``messages`` (chat history
        with roles ``user`` / ``assistant``). Assistant turns are sent as Gemini
        role ``model``.

        ``system_instruction`` is passed via ``GenerateContentConfig`` when supported.
        """
        from google.genai import types as genai_types

        resolved_model = (model or DEFAULT_VERTEX_TEXT_MODEL).strip()
        client = self._get_client()

        if messages is not None:
            contents = _openai_style_messages_to_contents(messages, genai_types=genai_types)
        elif prompt is not None:
            p = prompt.strip()
            if not p:
                raise ValueError("prompt is empty")
            contents = [
                genai_types.Content(
                    role="user",
                    parts=[genai_types.Part.from_text(text=p)],
                )
            ]
        else:
            raise ValueError("Provide either prompt= or messages=")

        config_kwargs: dict[str, Any] = {}
        if system_instruction and str(system_instruction).strip():
            config_kwargs["system_instruction"] = str(system_instruction).strip()
        if temperature is not None:
            config_kwargs["temperature"] = float(temperature)
        if max_output_tokens is not None:
            config_kwargs["max_output_tokens"] = int(max_output_tokens)

        config = (
            genai_types.GenerateContentConfig(**config_kwargs) if config_kwargs else None
        )

        response = client.models.generate_content(
            model=resolved_model,
            contents=contents,
            config=config,
        )

        text = _extract_text_from_response(response)
        usage = _usage_to_dict(getattr(response, "usage_metadata", None))

        return VertexGeminiInferResult(
            text=text,
            usage=usage,
            model=resolved_model,
            raw_response=response if include_raw_response else None,
        )


# Alias for callers who prefer a provider-agnostic name
GoogleAIInference = VertexGeminiText

__all__ = [
    "DEFAULT_VERTEX_TEXT_MODEL",
    "VertexGeminiInferResult",
    "VertexGeminiText",
    "GoogleAIInference",
]
