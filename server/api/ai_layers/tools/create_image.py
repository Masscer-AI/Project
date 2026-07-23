"""
Tool: create_image

Generates an image server-side and stores it as a MessageAttachment(kind="file"),
so it can be rendered in the frontend and later read via read_attachment().

This tool is only callable by the model when it's explicitly enabled via
AgentTask tool_names (see api/ai_layers/tools/TOOL_REGISTRY).
"""

from __future__ import annotations

import json as _json
import logging
import mimetypes
import base64
import os
import tempfile
import uuid
from typing import Literal

from django.core.files.base import ContentFile
from django.utils.text import slugify
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

AspectRatio = Literal["square", "landscape", "portrait"]

# ---------------------------------------------------------------------------
# Image model catalog — single source of truth for allowlist + AI guidance.
# ---------------------------------------------------------------------------

DEFAULT_IMAGE_MODEL = "gpt-image-2"

IMAGE_GENERATION_MODELS: tuple[dict[str, str], ...] = (
    {
        "slug": "gpt-image-2",
        "provider": "openai",
        "description": (
            "Best for long-running highest-quality images with clear rendered text."
        ),
    },
    {
        "slug": "gemini-3.1-flash-lite-image",
        "provider": "google",
        "description": (
            "Best for blazingly fast image generation at great quality "
            "(Nano Banana 2 Lite)."
        ),
    },
)

OPENAI_IMAGE_MODELS: set[str] = {
    m["slug"] for m in IMAGE_GENERATION_MODELS if m["provider"] == "openai"
}
GOOGLE_IMAGE_MODELS: set[str] = {
    m["slug"] for m in IMAGE_GENERATION_MODELS if m["provider"] == "google"
}
ALL_IMAGE_MODELS: set[str] = {m["slug"] for m in IMAGE_GENERATION_MODELS}


def _image_models_brief_lines() -> str:
    """slug + brief description for each catalog entry (one line each)."""
    return "\n".join(
        f"- {m['slug']}: {m['description']}" for m in IMAGE_GENERATION_MODELS
    )


def image_models_param_description() -> str:
    return (
        "Optional image model slug. Omit or pass null to use the default "
        f"({DEFAULT_IMAGE_MODEL}). Supported models:\n"
        f"{_image_models_brief_lines()}"
    )


def image_models_tool_description_snippet() -> str:
    return (
        f"Default model: {DEFAULT_IMAGE_MODEL}. "
        "Optionally pass `model` to choose among:\n"
        f"{_image_models_brief_lines()}"
    )


def image_models_agent_instructions_snippet() -> str:
    return (
        "If the user asks you to generate an image, call "
        "create_image(prompt, model, aspect_ratio, guidance_attachments). "
        f"`model` is optional and defaults to '{DEFAULT_IMAGE_MODEL}'. "
        "Choose a model when it matters:\n"
        f"{_image_models_brief_lines()}\n"
        "aspect_ratio must be one of: square, landscape, portrait. "
        "guidance_attachments is an optional list of MessageAttachment UUIDs "
        "for visual reference (supported by both models)."
    )


GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "masscer-492023")
# gemini-3.1-flash-lite-image is global-endpoint only (unlike Veo, which uses GOOGLE_CLOUD_LOCATION).
GOOGLE_IMAGE_LOCATION = "global"

_ASPECT_RATIO_TO_GOOGLE = {
    "square": "1:1",
    "landscape": "16:9",
    "portrait": "9:16",
}

_ASPECT_RATIO_TO_OPENAI = {
    "square": (1024, 1024),
    "landscape": (1536, 1024),
    "portrait": (1024, 1536),
}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CreateImageParams(BaseModel):
    prompt: str = Field(description="Text prompt to generate an image from.")
    model: str | None = Field(
        default=None,
        description=image_models_param_description(),
    )
    aspect_ratio: AspectRatio = Field(
        default="square",
        description="Aspect ratio choice: square|landscape|portrait.",
    )
    guidance_attachments: list[str] = Field(
        default=[],
        description=(
            "Optional list of MessageAttachment UUIDs to use as visual reference. "
            "Supported by both OpenAI and Google models."
        ),
    )


class CreateImageResult(BaseModel):
    attachment_id: str = Field(description="UUID of the created MessageAttachment.")
    name: str = Field(description="A short name for display (slugified).")
    content: str = Field(description="Display URL for the created attachment file.")
    model: str = Field(description="Model slug used.")
    aspect_ratio: AspectRatio = Field(description="Aspect ratio requested.")
    source_image_url: str = Field(description="Provider reference for the created image (debug/audit).")


# ---------------------------------------------------------------------------
# Small utilities
# ---------------------------------------------------------------------------

def _guess_filename(prompt: str, content_type: str | None) -> str:
    base = slugify((prompt or "").strip()[:80] or "image")
    ext = mimetypes.guess_extension((content_type or "").split(";")[0].strip()) or ".png"
    return f"{base}-{uuid.uuid4().hex[:8]}{ext}"


def _setup_google_credentials() -> str | None:
    """
    Write GOOGLE_APPLICATION_CREDENTIALS_JSON to a temp file, set
    GOOGLE_APPLICATION_CREDENTIALS, and return the temp path for cleanup.
    Returns None if the env var is absent.
    """
    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip().strip("'\"")
    if not credentials_json:
        return None

    if os.path.isfile(credentials_json):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_json
        return credentials_json

    try:
        _json.loads(credentials_json)
    except _json.JSONDecodeError as exc:
        raise ValueError(f"GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON: {exc}")

    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, prefix="gcp_creds_")
    tmp.write(credentials_json)
    tmp.close()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
    return tmp.name


def _load_guidance_attachments(attachment_ids: list[str], MessageAttachment) -> list:
    """Resolve a list of attachment UUIDs to MessageAttachment instances, skipping missing ones."""
    objects = []
    for att_id in attachment_ids or []:
        try:
            objects.append(MessageAttachment.objects.get(id=att_id, kind="file"))
        except MessageAttachment.DoesNotExist:
            logger.warning("Guidance attachment %s not found, skipping", att_id)
    return objects


# ---------------------------------------------------------------------------
# Provider-specific generators — each returns (raw_bytes, content_type)
# ---------------------------------------------------------------------------

def _generate_image_openai(
    *,
    prompt: str,
    model: str,
    aspect_ratio: AspectRatio,
    guidance_attachments: list,
) -> tuple[bytes, str]:
    """Generate via OpenAI. Uses images.edit() when guidance images are provided, generate() otherwise."""
    w, h = _ASPECT_RATIO_TO_OPENAI[aspect_ratio]
    size = f"{w}x{h}"
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    if guidance_attachments:
        image_files = [open(att.file.path, "rb") for att in guidance_attachments]
        try:
            resp = client.images.edit(
                model=model,
                image=image_files,
                prompt=prompt,
                size=size,
                quality="medium",
            )
        finally:
            for f in image_files:
                f.close()
    else:
        resp = client.images.generate(
            model=model,
            prompt=prompt,
            size=size,
            quality="medium",
        )

    b64 = resp.data[0].b64_json
    if not b64:
        raise ValueError("OpenAI returned empty image data")
    return base64.b64decode(b64), "image/png"


def _generate_image_google(
    *,
    prompt: str,
    model: str,
    aspect_ratio: AspectRatio,
    guidance_attachments: list,
) -> tuple[bytes, str]:
    """Generate via Google Gemini on Vertex AI using the service account credential."""
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ValueError("google-genai is not installed. Run: uv add google-genai")

    tmp_creds_path = _setup_google_credentials()
    try:
        client = genai.Client(
            vertexai=True,
            project=GOOGLE_CLOUD_PROJECT,
            location=GOOGLE_IMAGE_LOCATION,
        )

        parts = []
        for att in guidance_attachments:
            try:
                with open(att.file.path, "rb") as f:
                    image_bytes = f.read()
                parts.append(
                    genai_types.Part.from_bytes(
                        data=image_bytes,
                        mime_type=att.content_type or "image/png",
                    )
                )
            except Exception:
                logger.warning("Could not read guidance attachment %s, skipping", att.id)

        parts.append(genai_types.Part.from_text(text=prompt))

        config = genai_types.GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=genai_types.ImageConfig(
                aspect_ratio=_ASPECT_RATIO_TO_GOOGLE.get(aspect_ratio, "1:1"),
            ),
            safety_settings=[
                genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
                genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
                genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
                genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
            ],
        )

        response = client.models.generate_content(
            model=model,
            contents=[genai_types.Content(role="user", parts=parts)],
            config=config,
        )

        for part in response.parts:
            if part.inline_data and part.inline_data.data:
                data = part.inline_data.data
                if isinstance(data, str):
                    data = base64.b64decode(data)
                return data, part.inline_data.mime_type or "image/png"

        raise ValueError("Google Gemini returned no image data")
    finally:
        if tmp_creds_path and tmp_creds_path.startswith(tempfile.gettempdir()):
            try:
                os.unlink(tmp_creds_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Main implementation
# ---------------------------------------------------------------------------

def _create_image_impl(
    *,
    prompt: str,
    model: str | None,
    aspect_ratio: AspectRatio,
    guidance_attachments: list[str],
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> CreateImageResult:
    from django.conf import settings
    from django.contrib.auth.models import User

    from api.authenticate.services import FeatureFlagService
    from api.messaging.models import Conversation, MessageAttachment

    # ---- Validate ----
    model = (model or "").strip() or DEFAULT_IMAGE_MODEL
    if model not in ALL_IMAGE_MODELS:
        raise ValueError(
            f"Unsupported image model '{model}'. "
            f"Allowed: {', '.join(sorted(ALL_IMAGE_MODELS))}"
        )

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    # ---- Load conversation + user ----
    try:
        conversation = Conversation.objects.select_related("organization", "chat_widget").get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass

    # ---- Feature gate ----
    from api.ai_layers.tools.embedded_channels import conversation_uses_capability_gated_media_tools

    if not conversation_uses_capability_gated_media_tools(conversation):
        enabled, _reason = FeatureFlagService.is_feature_enabled(
            "image-tools",
            organization=getattr(conversation, "organization", None),
            user=user,
        )
        if not enabled:
            raise ValueError("The 'image-tools' feature is not enabled.")

    # ---- Load guidance attachments ----
    att_objects = _load_guidance_attachments(guidance_attachments, MessageAttachment)

    # ---- Generate ----
    try:
        if model in GOOGLE_IMAGE_MODELS:
            raw, content_type = _generate_image_google(
                prompt=prompt, model=model, aspect_ratio=aspect_ratio, guidance_attachments=att_objects,
            )
            source_image_url = f"google://{model}"
        else:
            raw, content_type = _generate_image_openai(
                prompt=prompt, model=model, aspect_ratio=aspect_ratio, guidance_attachments=att_objects,
            )
            source_image_url = f"openai://{model}"
    except Exception as e:
        logger.exception("Failed to generate image (model=%s)", model)
        raise ValueError(f"Failed to generate image: {e}")

    # ---- Resolve agent ----
    agent_obj = None
    if agent_slug:
        try:
            from api.ai_layers.models import Agent
            agent_obj = Agent.objects.get(slug=agent_slug)
        except Exception:
            pass

    # ---- Save attachment ----
    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent_obj,
        kind="file",
        file=ContentFile(raw, name=_guess_filename(prompt, content_type)),
        content_type=content_type,
        metadata={
            "prompt": prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "source_image_url": source_image_url,
        },
    )

    # ---- Bill ----
    if user_id is not None:
        try:
            from api.consumption.tasks import async_register_image_generation
            organization_id = getattr(conversation.organization, "id", None)
            async_register_image_generation.delay(user_id, model, organization_id)
        except Exception:
            logger.warning("Failed to queue image billing task", exc_info=True)

    # ---- Build display URL ----
    api_base = getattr(settings, "API_BASE_URL", None) or ""
    file_url = attachment.file.url if attachment.file else ""
    display_url = (
        f"{api_base.rstrip('/')}{file_url}"
        if api_base and file_url and not file_url.startswith("http")
        else file_url
    )

    return CreateImageResult(
        attachment_id=str(attachment.id),
        name=slugify(prompt[:100]) or "image",
        content=display_url,
        model=model,
        aspect_ratio=aspect_ratio,
        source_image_url=source_image_url,
    )


# ---------------------------------------------------------------------------
# Tool entry point
# ---------------------------------------------------------------------------

def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("create_image requires conversation_id in tool context")

    def create_image(
        prompt: str,
        model: str | None = None,
        aspect_ratio: AspectRatio = "square",
        guidance_attachments: list[str] | None = None,
    ) -> CreateImageResult:
        return _create_image_impl(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            guidance_attachments=guidance_attachments or [],
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "create_image",
        "description": (
            "Generate an image from a text prompt and store it as a conversation attachment. "
            "Use this ONLY when the user asks to generate an image. "
            f"{image_models_tool_description_snippet()} "
            "guidance_attachments is an optional list of MessageAttachment UUIDs to use as visual reference. "
            "Returns an attachment_id and a display URL (content) that will appear in the chat."
        ),
        "parameters": CreateImageParams,
        "function": create_image,
    }
