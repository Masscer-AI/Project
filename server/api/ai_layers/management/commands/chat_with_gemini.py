"""
Temporary dev command: talk to Vertex Gemini text models without AgentLoop.

Optional dev tool ``print_in_color`` (5 ANSI colors) to experiment with Gemini
function calling on Vertex — see ``--no-tools``.

Usage::

    cd server && uv run python manage.py chat_with_gemini

    uv run python manage.py chat_with_gemini --prompt "Print hello in red using your tool"

Requires the same env as :mod:`api.utils.vertex_gemini_text` (see module docstring).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

from django.core.management.base import BaseCommand

from api.utils.vertex_gemini_text import (
    DEFAULT_VERTEX_TEXT_MODEL,
    VertexGeminiText,
    _usage_to_dict,
)

# --- print_in_color tool (Gemini function declaration) -------------------------

PRINT_IN_COLOR_TOOL_NAME = "print_in_color"

_TERMINAL_COLORS = ("red", "green", "blue", "yellow", "magenta")

ANSI_CODES = {
    "red": "\033[91m",
    "green": "\033[92m",
    "blue": "\033[94m",
    "yellow": "\033[93m",
    "magenta": "\033[95m",
}
ANSI_RESET = "\033[0m"

_PRINT_TOOL_PARAMETERS_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "color": {
            "type": "string",
            "enum": list(_TERMINAL_COLORS),
            "description": "One of five terminal ANSI colors.",
        },
        "message": {"type": "string", "description": "Text to print to the user's terminal."},
    },
    "required": ["color", "message"],
}


def _build_print_in_color_tool(genai_types: Any) -> Any:
    fd = genai_types.FunctionDeclaration(
        name=PRINT_IN_COLOR_TOOL_NAME,
        description=(
            "Print a message in the user's terminal using a fixed ANSI color. "
            "Call this when the user asks you to print or display something in a given color."
        ),
        parameters_json_schema=_PRINT_TOOL_PARAMETERS_JSON_SCHEMA,
    )
    return genai_types.Tool(function_declarations=[fd])


def _merge_usage(acc: dict[str, int], usage_metadata: Any) -> None:
    d = _usage_to_dict(usage_metadata)
    for k in acc:
        acc[k] = acc.get(k, 0) + d.get(k, 0)


class Command(BaseCommand):
    help = (
        "[TEMP] Interactive Vertex Gemini via google-genai. "
        "Optional tool print_in_color (use --no-tools to disable). "
        "Not wired to AgentLoop."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--prompt",
            type=str,
            default=None,
            help="Send one message and exit (non-interactive).",
        )
        parser.add_argument(
            "--system",
            type=str,
            default="",
            dest="system_instruction",
            help="Optional system instruction (first turn only when tools off; first API call per turn when tools on).",
        )
        parser.add_argument(
            "--model",
            type=str,
            default=None,
            help=f"Override model id (default: {DEFAULT_VERTEX_TEXT_MODEL}).",
        )
        parser.add_argument(
            "--temperature",
            type=float,
            default=None,
            help="Optional sampling temperature.",
        )
        parser.add_argument(
            "--no-tools",
            action="store_true",
            help="Disable the print_in_color tool (tools are enabled by default).",
        )

    def handle(self, *args, **options):
        self._print_prerequisites()

        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
        if not project:
            self.stderr.write(
                self.style.ERROR(
                    "GOOGLE_CLOUD_PROJECT is not set. Export it or add it to your .env.\n"
                )
            )
            sys.exit(1)

        try:
            vx = VertexGeminiText()
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Could not init VertexGeminiText: {exc}\n"))
            sys.exit(1)

        model_slug = (options.get("model") or DEFAULT_VERTEX_TEXT_MODEL).strip()
        system_instruction = (options.get("system_instruction") or "").strip() or None
        temperature = options.get("temperature")
        single_prompt = options.get("prompt")
        use_tools = not options.get("no_tools")

        kw_infer: dict[str, Any] = {}
        if options.get("model"):
            kw_infer["model"] = model_slug
        if temperature is not None:
            kw_infer["temperature"] = float(temperature)

        try:
            if single_prompt is not None:
                text = single_prompt.strip()
                if not text:
                    self.stderr.write(self.style.ERROR("--prompt must not be empty.\n"))
                    sys.exit(1)
                if use_tools:
                    from google.genai import types as genai_types

                    contents = [
                        genai_types.Content(
                            role="user",
                            parts=[genai_types.Part.from_text(text=text)],
                        )
                    ]
                    reply, usage = self._generate_with_print_tool(
                        vx,
                        model_slug=model_slug,
                        contents=contents,
                        system_instruction_once=system_instruction,
                        temperature=temperature,
                        genai_types=genai_types,
                    )
                    self.stdout.write(reply + "\n")
                    self._print_usage_dict(usage)
                else:
                    out = vx.infer(
                        prompt=text,
                        system_instruction=system_instruction,
                        **kw_infer,
                    )
                    self.stdout.write(out.text + "\n")
                    self._print_usage_footer(out)
                return

            self.stdout.write(
                self.style.MIGRATE_HEADING(
                    "Chat with Gemini (type 'exit' or 'quit' to stop, Ctrl+C to abort)\n"
                )
            )
            if use_tools:
                self.stdout.write(
                    self.style.WARNING(
                        f"Tools enabled: model may call `{PRINT_IN_COLOR_TOOL_NAME}` "
                        f"(colors: {', '.join(_TERMINAL_COLORS)}). Use --no-tools to disable.\n\n"
                    )
                )

            system_sent = False
            vertex_contents: list[Any] = []
            messages: list[dict] = []

            while True:
                try:
                    line = input("You> ").strip()
                except EOFError:
                    self.stdout.write("\n")
                    break
                if not line:
                    continue
                low = line.lower()
                if low in ("exit", "quit", ":q"):
                    break

                messages.append({"role": "user", "content": line})

                si = system_instruction if not system_sent else None

                try:
                    if use_tools:
                        from google.genai import types as genai_types

                        vertex_contents.append(
                            genai_types.Content(
                                role="user",
                                parts=[genai_types.Part.from_text(text=line)],
                            )
                        )
                        reply, usage = self._generate_with_print_tool(
                            vx,
                            model_slug=model_slug,
                            contents=vertex_contents,
                            system_instruction_once=si,
                            temperature=temperature,
                            genai_types=genai_types,
                        )
                        if si:
                            system_sent = True
                        # Keep transcript for next turns (includes tool turns inside vertex_contents)
                        self.stdout.write(self.style.SUCCESS(f"Gemini> {reply}\n"))
                        self._print_usage_dict(usage)
                        messages.append({"role": "assistant", "content": reply})
                    else:
                        out = vx.infer(
                            messages=list(messages),
                            system_instruction=si,
                            **kw_infer,
                        )
                        if si:
                            system_sent = True
                        reply = out.text or "(empty reply)"
                        self.stdout.write(self.style.SUCCESS(f"Gemini> {reply}\n"))
                        messages.append({"role": "assistant", "content": reply})
                        self._print_usage_footer(out)
                except Exception as exc:
                    self.stderr.write(self.style.ERROR(f"Gemini error: {exc}\n"))
                    messages.pop()
                    if use_tools:
                        vertex_contents.pop()
                    continue
        finally:
            vx.close()

    def _dispatch_print_in_color(self, raw_args: Any) -> dict[str, Any]:
        args = raw_args
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                return {"ok": False, "error": "invalid function arguments"}
        if not isinstance(args, dict):
            return {"ok": False, "error": "arguments must be an object"}

        color = str(args.get("color") or "").strip().lower()
        message = args.get("message")
        if message is None:
            message = ""
        elif not isinstance(message, str):
            message = str(message)

        if color not in ANSI_CODES:
            return {"ok": False, "error": f"color must be one of {list(ANSI_CODES.keys())}"}

        ansi = ANSI_CODES[color]
        self.stdout.write(f"{ansi}{message}{ANSI_RESET}\n")
        return {"ok": True, "color": color, "printed_chars": len(message)}

    def _generate_with_print_tool(
        self,
        vx: VertexGeminiText,
        *,
        model_slug: str,
        contents: list[Any],
        system_instruction_once: str | None,
        temperature: float | None,
        genai_types: Any,
        max_tool_rounds: int = 16,
    ) -> tuple[str, dict[str, int]]:
        """
        Run generate_content in a loop until the model returns text (no function calls),
        dispatching print_in_color to the terminal.
        Mutates ``contents`` in place (Gemini conversation history).
        """
        client = vx._get_client()
        print_tool = _build_print_in_color_tool(genai_types)
        usage_acc: dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

        first_call_of_turn = True

        for _ in range(max_tool_rounds):
            cfg_kwargs: dict[str, Any] = {
                "tools": [print_tool],
                "tool_config": genai_types.ToolConfig(
                    function_calling_config=genai_types.FunctionCallingConfig(
                        mode=genai_types.FunctionCallingConfigMode.AUTO,
                    )
                ),
            }
            if temperature is not None:
                cfg_kwargs["temperature"] = float(temperature)
            if first_call_of_turn and system_instruction_once:
                cfg_kwargs["system_instruction"] = system_instruction_once.strip()

            config = genai_types.GenerateContentConfig(**cfg_kwargs)
            response = client.models.generate_content(
                model=model_slug,
                contents=contents,
                config=config,
            )
            first_call_of_turn = False
            _merge_usage(usage_acc, getattr(response, "usage_metadata", None))

            if not response.candidates:
                return ("(no response)", usage_acc)

            cand = response.candidates[0]

            if not cand.content or not cand.content.parts:
                return ("(empty content)", usage_acc)

            parts = list(cand.content.parts)
            function_calls = [p.function_call for p in parts if getattr(p, "function_call", None)]

            if function_calls:
                contents.append(cand.content)
                response_parts: list[Any] = []
                for fc in function_calls:
                    name = getattr(fc, "name", "") or ""
                    args = getattr(fc, "args", None)
                    call_id = getattr(fc, "id", None)
                    if name == PRINT_IN_COLOR_TOOL_NAME:
                        result = self._dispatch_print_in_color(args)
                    else:
                        result = {"ok": False, "error": f"unknown tool {name!r}"}

                    fr_kw: dict[str, Any] = {"name": name, "response": result}
                    if call_id:
                        fr_kw["id"] = call_id
                    fr = genai_types.FunctionResponse(**fr_kw)
                    response_parts.append(
                        genai_types.Part(function_response=fr)
                    )

                if response_parts:
                    contents.append(
                        genai_types.Content(role="user", parts=response_parts)
                    )
                continue

            text_chunks: list[str] = []
            for p in parts:
                tx = getattr(p, "text", None)
                if tx:
                    text_chunks.append(tx)
            text = "".join(text_chunks).strip()
            contents.append(cand.content)
            return (text or "(empty reply)", usage_acc)

        return ("(max tool rounds exceeded)", usage_acc)

    def _print_prerequisites(self) -> None:
        self.stdout.write(self.style.WARNING("--- Prerequisites (Vertex text) ---\n"))
        self.stdout.write(
            "  GOOGLE_CLOUD_PROJECT     — GCP project id (required).\n"
            "  VERTEX_TEXT_LOCATION     — defaults to 'global' for preview models.\n"
            "  Auth: ADC, or GOOGLE_APPLICATION_CREDENTIALS, or GOOGLE_APPLICATION_CREDENTIALS_JSON.\n"
            "  Docs: api.utils.vertex_gemini_text module docstring.\n\n"
        )

    def _print_usage_footer(self, out) -> None:
        u = out.usage or {}
        self._print_usage_dict(
            {
                "prompt_tokens": u.get("prompt_tokens", 0),
                "completion_tokens": u.get("completion_tokens", 0),
                "total_tokens": u.get("total_tokens", 0),
            }
        )

    def _print_usage_dict(self, u: dict[str, int]) -> None:
        pt = u.get("prompt_tokens", 0)
        ct = u.get("completion_tokens", 0)
        tt = u.get("total_tokens", 0)
        if tt or pt or ct:
            self.stdout.write(self.style.NOTICE(f"  [tokens in/out/total: {pt}/{ct}/{tt}]\n"))
