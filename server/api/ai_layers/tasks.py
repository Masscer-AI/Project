import logging
import os
import time
import traceback as tb
import json
import re
from celery import shared_task
from .actions import generate_agent_profile_picture

logger = logging.getLogger(__name__)

def _masked_secret_tail(secret: str | None, tail: int = 10) -> str:
    if not secret:
        return "<missing>"
    if len(secret) <= tail:
        return "*" * len(secret)
    return f"{'*' * (len(secret) - tail)}{secret[-tail:]}"

DEFAULT_MAX_MEMORY_MESSAGES = 100

def _resolve_max_memory_messages(user_id=None) -> int:
    """Return the user's max_memory_messages preference, or the product default."""
    if not user_id:
        return DEFAULT_MAX_MEMORY_MESSAGES
    from api.preferences.models import UserPreferences

    prefs = (
        UserPreferences.objects.filter(user_id=user_id)
        .values_list("max_memory_messages", flat=True)
        .first()
    )
    if prefs is None:
        return DEFAULT_MAX_MEMORY_MESSAGES
    return max(0, int(prefs))

def _serialize_prev_messages(conversation, before_message_id, limit=None, *, user_id=None):
    """Load and serialize prev messages for reproducibility.

    Bounded by ``UserPreferences.max_memory_messages`` (default 100) unless
    an explicit ``limit`` is passed.
    """
    from api.messaging.models import Message

    if limit is None:
        limit = _resolve_max_memory_messages(
            user_id
            if user_id is not None
            else getattr(conversation, "user_id", None)
        )

    qs = Message.objects.filter(
        conversation=conversation,
        id__lt=before_message_id,
    ).order_by("-id")[:limit]
    return [
        {
            "id": m.id,
            "type": m.type,
            "text": m.text,
            "versions": m.versions,
            "attachments": m.attachments or [],
        }
        for m in reversed(list(qs))
    ]

@shared_task
def async_generate_agent_profile_picture(agent_id: int):
    profile_picture_url = generate_agent_profile_picture(agent_id)
    return profile_picture_url

def _agent_clock_context(
    client_datetime: dict | None,
    *,
    organization_id: int | None = None,
) -> str:
    """
    Text appended to agent instructions so the model can resolve relative times
    ("in 2 hours", "tomorrow").

    Cascade: user device clock → organization timezone clock → server clock.
    """
    from datetime import datetime, timezone as dt_timezone

    from api.ai_layers.tools.calendar_tool_helpers import (
        format_org_timezone_clock_line,
        resolve_org_timezone,
    )

    if isinstance(client_datetime, dict):
        loc = client_datetime.get("local_datetime_long")
        tz = client_datetime.get("timezone")
        utc = client_datetime.get("utc_iso")
        locale = client_datetime.get("locale")
        loc = loc.strip()[:500] if isinstance(loc, str) and loc.strip() else None
        tz = tz.strip()[:120] if isinstance(tz, str) and tz.strip() else None
        utc = utc.strip()[:80] if isinstance(utc, str) and utc.strip() else None
        locale = locale.strip()[:40] if isinstance(locale, str) and locale.strip() else None
        parts: list[str] = []
        if loc:
            parts.append(f"User's local date and time (their device): {loc}.")
        if tz:
            parts.append(f"User's IANA timezone: {tz}.")
        if utc:
            parts.append(f"Same instant (UTC, ISO-8601): {utc}.")
        if locale:
            parts.append(f"User locale: {locale}.")
        if parts:
            parts.append(
                "Interpret relative dates and times (e.g. 'in 2 hours', 'tomorrow', 'next Monday') "
                "using the user's local clock and timezone above."
            )
            if organization_id is not None:
                parts.append(format_org_timezone_clock_line(organization_id))
            return "\n".join(parts)

    if organization_id is not None:
        from zoneinfo import ZoneInfo

        tz_name = resolve_org_timezone(organization_id)
        try:
            tzinfo = ZoneInfo(tz_name)
        except Exception:
            tzinfo = ZoneInfo("UTC")
            tz_name = "UTC"
        now_utc = datetime.now(dt_timezone.utc)
        now_local = now_utc.astimezone(tzinfo)
        local_long = now_local.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z").replace(
            " 0", " "
        )
        return "\n".join(
            [
                "No client clock was provided; using the organization timezone as the default clock.",
                f"Current date and time in organization timezone ({tz_name}): {local_long}.",
                f"Organization IANA timezone: {tz_name}.",
                f"Same instant (UTC, ISO-8601): {now_utc.isoformat().replace('+00:00', 'Z')}.",
                "Interpret relative dates and times (e.g. 'in 2 hours', 'tomorrow', 'next Monday') "
                "using the organization clock and timezone above.",
                format_org_timezone_clock_line(organization_id),
            ]
        )

    server = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return "\n".join(
        [
            f"The current date and time (server) is {server}.",
            "No client clock or organization timezone was available; use this for relative "
            "time if needed, or ask the user to clarify their timezone.",
        ]
    )

def _conversation_tags_instruction_block(conversation, organization_id: int) -> str:
    """
    Human-readable current tags for the agent prompt, plus whether tagging is still required.

    Returns text to append under === CONVERSATION TAGS ===.
    """
    from api.messaging.models import Tag

    raw = getattr(conversation, "tags", None) or []
    stored_ids: list[int] = []
    if isinstance(raw, list):
        for t in raw:
            try:
                stored_ids.append(int(t))
            except (TypeError, ValueError):
                continue
    stored_ids = stored_ids[:3]

    if not stored_ids:
        return (
            "Current conversation tags: **none** (no tag ids stored on this conversation yet).\n"
            "Tag assignment state: **needs tags** — see rules below.\n"
            "After you assign tag ids, those integers are what you pass to get_tag_context(tag_id=…) for cross-thread context.\n"
        )

    rows = list(
        Tag.objects.filter(
            id__in=stored_ids,
            organization_id=organization_id,
            enabled=True,
        ).values("id", "title")
    )
    id_to_title = {r["id"]: r["title"] for r in rows}
    lines: list[str] = ["Current conversation tags (id and title, in order):"]
    any_resolved = False
    for tid in stored_ids:
        title = id_to_title.get(tid)
        if title is not None:
            any_resolved = True
            lines.append(f"- tag_id={tid} title={title!r}")
        else:
            lines.append(
                f"- tag_id={tid} (not found, disabled, or not in this organization — replace this id)"
            )

    if not any_resolved:
        lines.append(
            "Tag assignment state: **needs tags** — stored ids are missing or invalid; "
            "you must assign 1–3 valid organization tags."
        )
    else:
        lines.append(
            "Tag assignment state: **has tags** — refine only if the latest user message clearly warrants it."
        )
    lines.append(
        "The tag_id numbers above are the exact integers to pass to get_tag_context(tag_id=…) "
        "(not the title strings)."
    )
    return "\n".join(lines) + "\n"

def _conversation_summary_instruction_block(conversation) -> str:
    """
    Current stored summary for the agent prompt + when to call change_conversation_summary.
    """
    raw = getattr(conversation, "summary", None)
    text = raw.strip() if isinstance(raw, str) else ""
    if not text:
        current = "Current conversation summary: **(empty — none stored yet).**"
        state = (
            "Summary state: **needs a summary** once there is enough substance in the thread "
            "(not for pure greetings or empty turns alone)."
        )
    else:
        preview = text[:4000]
        if len(text) > 4000:
            preview += "\n… (truncated for this prompt)"
        current = f"Current conversation summary (verbatim):\n{preview}"
        state = (
            "Summary state: **has summary** — only replace it if the conversation’s main topic or "
            "purpose has **clearly** changed; do not refresh for small clarifications or tangents."
        )
    return (
        f"{current}\n"
        f"{state}\n"
        "Tool: **change_conversation_summary** — pass a single `summary` string (concise, 1–4 sentences when possible; "
        "same language as the conversation when possible).\n"
        "Rules:\n"
        "- Call **only** when the summary is empty/whitespace **or** the thread’s central focus has definitely shifted.\n"
        "- **Do not** call on every turn; if the existing summary still fits, skip the tool.\n"
    )

def _build_user_message_text(user_inputs: list[dict]) -> str:
    """
    Build a plain-text user message from user_inputs.
    Only includes input_text; images and documents are referenced via attachments/tool.
    """
    parts = []
    for inp in user_inputs:
        if inp.get("type") == "input_text":
            text = inp.get("text", "").strip()
            if text:
                parts.append(text)
    return "\n".join(parts) if parts else ""

def _format_attachments_for_model_context(attachments: list[dict]) -> str:
    """
    Render attachment metadata as plain text for model context.

    This is used when building the AgentLoop inputs so the model can discover
    attachment IDs from previous turns, without mutating stored Message.text.
    """
    if not attachments:
        return ""

    lines = ["Attachments available from this message:"]
    for a in attachments:
        a_type = a.get("type") or "attachment"
        aid = a.get("attachment_id") or a.get("id") or ""
        name = a.get("name") or ""
        url = a.get("content") if a_type == "website" else ""

        bits = [a_type]
        if name:
            bits.append(f"name={name}")
        if url:
            bits.append(f"url={url}")
        if aid:
            bits.append(f"attachment_id={aid}")
        lines.append("- " + " | ".join(bits))

    return "\n".join(lines)

def _agent_loop_provider_from_llm(llm) -> str:
    """Return :class:`~api.ai_layers.agent_loop.AgentLoop` provider: ``openai`` or ``google``."""
    if llm is None:
        return "openai"
    provider = getattr(llm, "provider", None)
    if provider is None:
        return "openai"
    name = (getattr(provider, "name", None) or "").strip().lower()
    if name == "google":
        return "google"
    return "openai"

def _build_agent_loop_inputs(
    *,
    prev_messages: list[dict],
    current_user_text: str,
    current_user_attachments: list[dict],
    agent_slug: str,
    multiagentic_modality: str,
    tag_other_agent_versions: bool = False,
) -> list[dict]:
    """
    Build the ordered OpenAI input messages for AgentLoop, including previous turns.

    We include attachment metadata inside the message content so the model can
    reference attachment IDs across many turns.

    When ``tag_other_agent_versions`` is True (agent handoff continuation), other
    agents' assistant versions are tagged as user-role turns (same as grupal)
    so the receiving agent does not treat them as its own prior replies.
    """
    inputs: list[dict] = []
    use_tagged_others = (
        multiagentic_modality == "grupal" or tag_other_agent_versions
    )

    for m in prev_messages or []:
        m_type = m.get("type")
        attachments_block = _format_attachments_for_model_context(m.get("attachments") or [])

        if m_type == "user":
            text = m.get("text") or ""
            if attachments_block:
                text = f"{text}\n\n{attachments_block}"
            inputs.append({"role": "user", "content": text})
            continue

        if m_type == "assistant":
            versions = m.get("versions") or []

            if use_tagged_others and versions:
                for v in versions:
                    v_text = v.get("text") or ""
                    if not v_text:
                        continue
                    if v.get("agent_slug") == agent_slug:
                        text = v_text
                        if attachments_block:
                            text = f"{text}\n\n{attachments_block}"
                        inputs.append({"role": "assistant", "content": text})
                    else:
                        agent_name = v.get("agent_name", "Unknown")
                        tagged = (
                            f"[GROUP CHAT — message from AI assistant \"{agent_name}\"]\n\n"
                            f"{v_text}"
                        )
                        if attachments_block:
                            tagged = f"{tagged}\n\n{attachments_block}"
                        inputs.append({"role": "user", "content": tagged})
                continue

            picked = None
            for v in versions:
                if v.get("agent_slug") == agent_slug and v.get("text"):
                    picked = v.get("text")
                    break
            text = picked or (m.get("text") or "")
            if attachments_block:
                text = f"{text}\n\n{attachments_block}"
            inputs.append({"role": "assistant", "content": text})
            continue

    final_text = current_user_text or ""
    current_block = _format_attachments_for_model_context(current_user_attachments or [])
    if current_block:
        final_text = f"{final_text}\n\n{current_block}"
    inputs.append({"role": "user", "content": final_text})

    return inputs

def _resolve_user_inputs_and_attachments(
    user_inputs: list[dict],
    conversation_id: str | None = None,
):
    """
    Normalize user_inputs to the minimal agent-task contract:
    - input_text
    - input_attachment { attachment_id }

    Also builds Message.attachments JSON for display and returns MessageAttachment
    objects to link to the saved Message.
    """
    from api.messaging.models import MessageAttachment
    from django.conf import settings

    resolved: list[dict] = []
    message_attachments: list[dict] = []
    attachment_objects: list[MessageAttachment] = []

    def _display_url_for_file(att: MessageAttachment) -> str:
        if not att.file:
            return ""
        api_base = getattr(settings, "API_BASE_URL", None) or ""
        url = att.file.url
        if api_base and not url.startswith("http"):
            return f"{api_base.rstrip('/')}{url}"
        return url

    for inp in user_inputs:
        input_type = inp.get("type", "")

        if input_type == "input_text":
            resolved.append({"type": "input_text", "text": inp.get("text", "")})
            continue

        if input_type == "input_attachment":
            attachment_id = inp.get("attachment_id")
            if not attachment_id:
                raise ValueError("input_attachment requires attachment_id")
            try:
                if conversation_id:
                    att = MessageAttachment.objects.get(
                        id=attachment_id,
                        conversation_id=conversation_id,
                    )
                else:
                    att = MessageAttachment.objects.get(id=attachment_id)
            except MessageAttachment.DoesNotExist:
                raise ValueError(
                    f"MessageAttachment {attachment_id} not found"
                    + (f" for conversation {conversation_id}" if conversation_id else "")
                )

            attachment_objects.append(att)
            resolved.append({"type": "input_attachment", "attachment_id": str(att.id)})

            kind = getattr(att, "kind", "") or ""
            if kind == "website":
                message_attachments.append(
                    {
                        "type": "website",
                        "content": getattr(att, "url", "") or "",
                        "attachment_id": str(att.id),
                    }
                )
            elif kind == "rag_document":
                rag_doc = getattr(att, "rag_document", None)
                message_attachments.append(
                    {
                        "type": "rag_document",
                        "name": getattr(rag_doc, "name", None) if rag_doc else None,
                        "attachment_id": str(att.id),
                    }
                )
            else:
                display_url = _display_url_for_file(att)
                is_image = bool(att.content_type and att.content_type.startswith("image/"))
                filename = (
                    att.file.name.split("/")[-1]
                    if att.file and att.file.name
                    else ("image" if is_image else "document")
                )
                message_attachments.append(
                    {
                        "type": "image" if is_image else "document",
                        "content": display_url,
                        "name": filename,
                        "attachment_id": str(att.id),
                    }
                )
            continue

        raise ValueError(f"Unsupported user input type '{input_type}'")

    return resolved, message_attachments, attachment_objects

def _extract_create_image_attachments(tool_calls: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Extract image attachment descriptors from AgentLoop tool_calls.

    create_image tool returns JSON like:
      { attachment_id, name, content, ... }

    We persist those into Message.attachments (for UI) and keep attachment IDs
    to link MessageAttachment.message after the assistant Message exists.
    """
    if not tool_calls:
        return [], []

    attachments: list[dict] = []
    attachment_ids: list[str] = []

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "create_image":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            tool_payload = json.loads(raw)
            if not isinstance(tool_payload, dict):
                continue
            aid = tool_payload.get("attachment_id")
            content = tool_payload.get("content") or ""
            name = tool_payload.get("name") or "image"
            if not aid or not content:
                continue
            attachments.append(
                {
                    "type": "image",
                    "content": content,
                    "name": name,
                    "attachment_id": str(aid),
                }
            )
            attachment_ids.append(str(aid))
        except Exception:
            continue

    return attachments, attachment_ids

def _extract_create_speech_attachments(tool_calls: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Extract audio attachment descriptors from AgentLoop tool_calls.

    create_speech tool returns JSON like:
      { attachment_id, name, content, content_type, ... }
    """
    if not tool_calls:
        return [], []

    attachments: list[dict] = []
    attachment_ids: list[str] = []

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "create_speech":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            tool_payload = json.loads(raw)
            if not isinstance(tool_payload, dict):
                continue
            aid = tool_payload.get("attachment_id")
            content = tool_payload.get("content") or ""
            name = tool_payload.get("name") or "speech"
            if not aid or not content:
                continue
            attachments.append(
                {
                    "type": "audio_generation",
                    "content": content,
                    "name": name,
                    "attachment_id": str(aid),
                }
            )
            attachment_ids.append(str(aid))
        except Exception:
            continue

    return attachments, attachment_ids

def _extract_generate_dialogue_attachments(tool_calls: list[dict]) -> tuple[list[dict], list[str]]:
    """Extract audio attachment descriptors returned by generate_dialogue."""
    if not tool_calls:
        return [], []

    attachments: list[dict] = []
    attachment_ids: list[str] = []
    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "generate_dialogue":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            tool_payload = json.loads(raw)
            if not isinstance(tool_payload, dict):
                continue
            aid = tool_payload.get("attachment_id")
            content = tool_payload.get("content") or ""
            name = tool_payload.get("name") or "dialogue"
            if not aid or not content:
                continue
            attachments.append(
                {
                    "type": "audio_generation",
                    "content": content,
                    "name": name,
                    "attachment_id": str(aid),
                }
            )
            attachment_ids.append(str(aid))
        except Exception:
            continue

    return attachments, attachment_ids

def _extract_generate_video_attachments(tool_calls: list[dict]) -> tuple[list[dict], list[str]]:
    """
    Extract video attachment descriptors from AgentLoop tool_calls.

    generate_video tool returns JSON like:
      { attachment_id, name, content, model, duration_seconds, ... }
    """
    if not tool_calls:
        return [], []

    attachments: list[dict] = []
    attachment_ids: list[str] = []

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "generate_video":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            tool_payload = json.loads(raw)
            if not isinstance(tool_payload, dict):
                continue
            aid = tool_payload.get("attachment_id")
            content = tool_payload.get("content") or ""
            name = tool_payload.get("name") or "video"
            if not aid or not content:
                continue
            attachments.append(
                {
                    "type": "video/mp4",
                    "content": content,
                    "name": name,
                    "attachment_id": str(aid),
                }
            )
            attachment_ids.append(str(aid))
        except Exception:
            continue

    return attachments, attachment_ids

def _extract_generated_document_attachments(
    tool_calls: list[dict],
    *,
    tool_names: tuple[str, ...],
    default_name: str = "document",
) -> tuple[list[dict], list[str]]:
    """
    Extract document attachment descriptors from document-generation tool calls.

    Supported tools return JSON like:
      { attachment_id, name, content, content_type, ... }
    """
    if not tool_calls:
        return [], []

    attachments: list[dict] = []
    attachment_ids: list[str] = []

    for call in tool_calls:
        try:
            tool_name = (call or {}).get("tool_name")
            if tool_name not in tool_names:
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            tool_payload = json.loads(raw)
            if not isinstance(tool_payload, dict):
                continue
            aid = tool_payload.get("attachment_id")
            content = tool_payload.get("content") or ""
            name = tool_payload.get("name") or default_name
            if not aid or not content:
                continue
            attachments.append(
                {
                    "type": "document",
                    "content": content,
                    "name": name,
                    "attachment_id": str(aid),
                }
            )
            attachment_ids.append(str(aid))
        except Exception:
            continue

    return attachments, attachment_ids

def _extract_render_document_template_attachments(
    tool_calls: list[dict],
) -> tuple[list[dict], list[str]]:
    """
    Extract document attachment descriptors from render_document_template tool calls.

    render_document_template returns JSON like:
      { attachment_id, name, content, content_type, ... }
    """
    if not tool_calls:
        return [], []

    attachments: list[dict] = []
    attachment_ids: list[str] = []

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "render_document_template":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            tool_payload = json.loads(raw)
            if not isinstance(tool_payload, dict):
                continue
            aid = tool_payload.get("attachment_id")
            content = tool_payload.get("content") or ""
            name = tool_payload.get("name") or "document.docx"
            if not aid or not content:
                continue
            attachments.append(
                {
                    "type": "document",
                    "content": content,
                    "name": name,
                    "attachment_id": str(aid),
                }
            )
            attachment_ids.append(str(aid))
        except Exception:
            continue

    return attachments, attachment_ids

def _extract_generate_document_file_attachments(
    tool_calls: list[dict],
) -> tuple[list[dict], list[str]]:
    return _extract_generated_document_attachments(
        tool_calls,
        tool_names=("generate_document_file",),
        default_name="document.docx",
    )

def _extract_generate_excel_file_attachments(
    tool_calls: list[dict],
) -> tuple[list[dict], list[str]]:
    return _extract_generated_document_attachments(
        tool_calls,
        tool_names=("generate_excel_file",),
        default_name="spreadsheet.xlsx",
    )

def _extract_generate_gamma_attachment_attachments(
    tool_calls: list[dict],
) -> tuple[list[dict], list[str]]:
    return _extract_generated_document_attachments(
        tool_calls,
        tool_names=("generate_gamma_attachment", "generate_gamma_presentation"),
        default_name="presentation.pdf",
    )

def _message_attachment_to_display_dict(att) -> dict | None:
    """
    Build a Message.attachments-compatible descriptor from a MessageAttachment row.
    """
    from django.conf import settings

    kind = getattr(att, "kind", "") or ""
    aid = str(att.id)

    if kind == "website":
        return {
            "type": "website",
            "content": getattr(att, "url", "") or "",
            "attachment_id": aid,
        }

    if kind == "rag_document":
        rag_doc = getattr(att, "rag_document", None)
        return {
            "type": "rag_document",
            "name": getattr(rag_doc, "name", None) if rag_doc else None,
            "attachment_id": aid,
        }

    file_field = getattr(att, "file", None)
    if not file_field:
        return None

    url = file_field.url
    api_base = getattr(settings, "API_BASE_URL", None) or ""
    if api_base and isinstance(url, str) and not url.startswith("http"):
        url = f"{api_base.rstrip('/')}{url}"

    ctype = getattr(att, "content_type", "") or ""
    if ctype.startswith("image/"):
        att_type = "image"
    elif ctype.startswith("audio/"):
        att_type = "audio_generation"
    elif ctype.startswith("video/"):
        att_type = ctype
    else:
        att_type = "document"

    filename = (
        file_field.name.split("/")[-1]
        if getattr(file_field, "name", None)
        else (
            "image"
            if att_type == "image"
            else "video"
            if isinstance(att_type, str) and att_type.startswith("video/")
            else "document"
        )
    )

    return {
        "type": att_type,
        "content": url,
        "name": filename,
        "attachment_id": aid,
        "id": aid,
        "visibility": getattr(att, "visibility", None) or "personal",
    }

def _extract_referenced_attachments_from_text(
    text: str,
    conversation_id: str,
) -> list[dict]:
    """
    Resolve attachment:<uuid> references found in assistant output text and return
    their display descriptors so frontend markdown rendering can resolve them.
    """
    if not text:
        return []

    ids = re.findall(
        r"attachment:([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})",
        text,
    )
    if not ids:
        return []

    ordered_ids: list[str] = []
    seen: set[str] = set()
    for aid in ids:
        if aid in seen:
            continue
        seen.add(aid)
        ordered_ids.append(aid)

    from api.messaging.models import MessageAttachment

    rows = MessageAttachment.objects.filter(
        conversation_id=conversation_id,
        id__in=ordered_ids,
    )
    by_id = {str(r.id): r for r in rows}

    resolved: list[dict] = []
    for aid in ordered_ids:
        row = by_id.get(aid)
        if not row:
            continue
        descriptor = _message_attachment_to_display_dict(row)
        if descriptor:
            resolved.append(descriptor)
    return resolved

def _extract_rag_sources(tool_calls: list[dict]) -> list[dict]:
    """
    Extract RAG sources from rag_query tool calls so they can be displayed
    in the frontend just like the streaming path does.

    Returns a list of source dicts matching the TSource frontend type:
      { model_id, model_name, content, extra }
    """
    if not tool_calls:
        return []

    sources: list[dict] = []
    seen: set[str] = set()

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "rag_query":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            tool_payload = json.loads(raw)
            if not isinstance(tool_payload, dict):
                continue
            results_wrapper = tool_payload.get("results") or {}
            inner = results_wrapper.get("results") or results_wrapper
            metadatas = inner.get("metadatas") or []
            for meta_list in metadatas:
                for meta in meta_list:
                    if not isinstance(meta, dict) or not meta:
                        continue
                    key = f"{meta.get('model_name', '')}-{meta.get('model_id', '')}"
                    if key in seen:
                        continue
                    seen.add(key)
                    sources.append({
                        "model_id": meta.get("model_id"),
                        "model_name": meta.get("model_name", "chunk"),
                        "content": meta.get("content", ""),
                        "extra": meta.get("extra", ""),
                    })
        except Exception:
            continue

    return sources

def _completion_to_message_attachment_dict(completion) -> dict:
    """Descriptor for Message.attachments so the client can show completion metadata."""
    from api.finetuning.models import Completion as CompletionModel

    assert isinstance(completion, CompletionModel)
    prompt_preview = (completion.prompt or "").strip()
    if len(prompt_preview) > 120:
        prompt_preview = prompt_preview[:117] + "..."
    return {
        "type": "completion",
        "id": completion.id,
        "completion_id": completion.id,
        "content": f"completion:{completion.id}",
        "name": prompt_preview or "Training example",
        "prompt": completion.prompt or "",
        "answer": completion.answer or "",
        "approved": bool(completion.approved),
    }

def _extract_create_completion_refs_from_tool_calls(tool_calls: list[dict]) -> list[dict]:
    """Collect completion descriptors from create_completion tool results."""
    if not tool_calls:
        return []

    from api.finetuning.models import Completion

    out: list[dict] = []
    seen: set[int] = set()

    for call in tool_calls:
        try:
            if (call or {}).get("tool_name") != "create_completion":
                continue
            raw = (call or {}).get("result") or ""
            if not isinstance(raw, str) or not raw.strip():
                continue
            tool_payload = json.loads(raw)
            if not isinstance(tool_payload, dict):
                continue
            cid = tool_payload.get("completion_id")
            if cid is None:
                continue
            cid = int(cid)
            if cid in seen:
                continue
            seen.add(cid)
            try:
                completion = Completion.objects.get(id=cid)
            except Completion.DoesNotExist:
                continue
            out.append(_completion_to_message_attachment_dict(completion))
        except Exception:
            continue

    return out

def _extract_referenced_completions_from_text(text: str, user) -> list[dict]:
    """
    Resolve completion:<id> references in assistant markdown for accessible completions.
    """
    if not text or user is None:
        return []

    ids = re.findall(r"completion:(\d+)", text)
    if not ids:
        return []

    ordered_ids: list[int] = []
    seen: set[int] = set()
    for raw in ids:
        try:
            cid = int(raw)
        except ValueError:
            continue
        if cid in seen:
            continue
        seen.add(cid)
        ordered_ids.append(cid)

    from django.db.models import Q

    from api.ai_layers.access import get_user_organization
    from api.finetuning.models import Completion

    user_org = get_user_organization(user)
    if user_org:
        base_qs = Completion.objects.filter(
            Q(assignments__agent__user=user)
            | Q(assignments__agent__organization=user_org)
        ).distinct()
    else:
        base_qs = Completion.objects.filter(assignments__agent__user=user).distinct()

    rows = {c.id: c for c in base_qs.filter(id__in=ordered_ids)}
    out: list[dict] = []
    for cid in ordered_ids:
        row = rows.get(cid)
        if not row:
            continue
        out.append(_completion_to_message_attachment_dict(row))
    return out

GENERAL_RULES = """
When referencing an attachment inside your message markdown, prefer this format:
"![Alt text](attachment:<attachment_id>). Do NOT invent /media/... URLs.

To link a saved training example (from create_completion), use:
"[Edit training example](completion:<completion_id>)" where completion_id is the integer returned by the tool.
Do NOT invent completion ids.

create_completion uses the finetuning "prompt" field as a CUE (when this row applies / retrieval hint),
and "answer" as the PAYLOAD (what to apply: reply text to prefer, facts to memorize, style rules, fixed openings, etc.).
They are NOT required to mimic a literal user message + next chat reply.
"""

@shared_task
def conversation_agent_task(
    conversation_id: str,
    user_inputs: list[dict],
    tool_names: list[str],
    agent_slugs: list[str],
    plugin_slugs: list[str] | None = None,
    multiagentic_modality: str = "isolated",
    max_iterations: int = 10,
    user_id: int | str | None = None,
    regenerate_message_id: int | None = None,
    client_datetime: dict | None = None,
    user_message_metadata: dict | None = None,
    capabilities_override: list[str] | None = None,
    tool_names_by_agent: dict[str, list[str]] | None = None,
    skip_persist_user_message: bool = False,
    existing_user_message_id: int | None = None,
):
    """
    Celery task that runs an AgentLoop for one or more agents in a conversation.

    Resolves agents from their slugs, derives instructions and model for each,
    executes the agent loop for each (sequentially), and emits real-time status
    updates via Redis pub/sub (notify_user) so the frontend can show progress.

    For multiagentic_modality="grupal", each agent sees previous agents' outputs
    as context. For "isolated", each agent only sees the user message.

    Args:
        conversation_id: UUID of the conversation
        user_inputs: list of input dicts, e.g. [{"type": "input_text", "text": "..."}]
        tool_names: list of tool names to resolve from the registry, shared by
            every agent in agent_slugs unless overridden per-agent below.
        agent_slugs: list of Agent slugs to run (in order)
        multiagentic_modality: "isolated" or "grupal"
        user_id: Notification route id (user id or widget_session:<id>)
        regenerate_message_id: if set, reuse this user message (update its text,
            delete all subsequent messages) instead of creating a new one.
        client_datetime: optional dict from the user's browser (utc_iso, timezone,
            local_datetime_long, locale) to resolve relative times in their locale.
        user_message_metadata: optional metadata merged onto the user Message
            (e.g. scheduled_task source markers). For agent_handoff continuations
            this is task-only context and is not written onto the user Message.
        capabilities_override: optional authoritative capability allowlist (e.g.
            scheduled-task snapshot). When set, auto-injection cannot add tools
            outside this list; runtime safety filters still apply.
        tool_names_by_agent: optional {agent_slug: tool_names} map. When an
            agent's slug is present here, its list replaces the shared
            tool_names for that agent only. Agents not in the map fall back to
            tool_names. Ignored (like tool_names) when capabilities_override
            is set, since that override is authoritative for every agent.
        skip_persist_user_message: when True with existing_user_message_id,
            reuse that user Message without creating/deleting messages (handoff).
        existing_user_message_id: user Message pk to attach AgentSessions to
            when skip_persist_user_message is True.

    Returns:
        dict with status, output, iterations, tool_calls_count, message_id, user_message_id
    """
    from api.ai_layers.agent_loop import AgentLoop
    from api.ai_layers.models import Agent, AgentSession
    from api.ai_layers.plugins import format_available_plugins_summary
    from api.ai_layers.tools import resolve_tools
    from api.ai_layers.schemas import (
        AgentSessionInputs,
        AgentSessionOutputs,
        AgentRef,
        ModelRef,
        OutputValue,
        OutputError,
    )
    from api.notify.actions import notify_user
    from api.messaging.models import Conversation, Message
    from api.messaging.schedule_helpers import normalize_capability_names
    notification_route_id = user_id
    actor_user_id = user_id if isinstance(user_id, int) else None

    logger.info(
        "conversation_agent_task received conversation=%s user=%s agents=%s "
        "tools=%s modality=%s skip_persist=%s",
        conversation_id,
        user_id,
        agent_slugs,
        tool_names,
        multiagentic_modality,
        skip_persist_user_message,
    )

    try:
        conversation = Conversation.objects.select_related(
            "organization",
            "user",
            "chat_widget",
            "chat_widget__agent",
            "ws_number",
            "ws_number__agent",
            "ws_contact",
        ).get(id=conversation_id)
    except Conversation.DoesNotExist:
        logger.error("Conversation %s not found", conversation_id)
        notify_user(
            notification_route_id,
            "agent_events_channel",
            {"type": "error", "conversation_id": conversation_id, "error": f"Conversation {conversation_id} not found"},
        )
        from api.ai_layers.agent_task_helpers import clear_agent_task_active

        clear_agent_task_active(conversation_id)
        return {"status": "error", "error": "Conversation not found"}

    is_widget_chat = conversation.chat_widget_id is not None
    is_whatsapp_chat = conversation.ws_number_id is not None
    is_embedded_channel = is_widget_chat or is_whatsapp_chat

    if actor_user_id is None and is_whatsapp_chat:
        contact = getattr(conversation, "ws_contact", None)
        if contact is not None and contact.user_id:
            actor_user_id = int(contact.user_id)
            logger.info(
                "conversation_agent_task: linked WhatsApp contact user=%s conversation=%s",
                actor_user_id,
                conversation_id,
            )

    override_allowlist: frozenset[str] | None = None
    if capabilities_override is not None:
        normalized_override = normalize_capability_names(capabilities_override)
        override_allowlist = frozenset(normalized_override)
        tool_names = list(normalized_override)
        tool_names_by_agent = None

    conv_metadata = conversation.metadata or {}
    is_mcp_chat = conv_metadata.get("source") == "mcp"
    mcp_tool_allowlist = frozenset(tool_names or [])

    def _may_auto_inject_tool(tool: str) -> bool:
        if override_allowlist is not None and tool not in override_allowlist:
            return False
        if not is_mcp_chat:
            return True
        return tool in mcp_tool_allowlist

    from api.messaging.takeover import is_takeover_active

    if is_takeover_active(conversation):
        logger.info(
            "conversation_agent_task skipped: takeover active conversation=%s",
            conversation_id,
        )
        from api.ai_layers.agent_task_helpers import clear_agent_task_active

        clear_agent_task_active(conversation_id)
        return {"status": "skipped", "reason": "takeover_active"}

    try:
        resolved_inputs, message_attachments, attachment_objects = _resolve_user_inputs_and_attachments(
            user_inputs, conversation_id=conversation_id
        )
    except ValueError as e:
        notify_user(
            notification_route_id,
            "agent_events_channel",
            {"type": "error", "conversation_id": conversation_id, "error": str(e)},
        )
        from api.ai_layers.agent_task_helpers import clear_agent_task_active

        clear_agent_task_active(conversation_id)
        return {"status": "error", "error": str(e)}
    user_message_text = _build_user_message_text(resolved_inputs)

    def emit_event(event_type: str, event_data: dict) -> None:
        payload = {"type": event_type, "conversation_id": conversation_id, **event_data}
        notify_user(notification_route_id, "agent_events_channel", payload)

    def emit_finished(event_data: dict) -> None:
        if not event_data.get("next_agent_slug"):
            from api.ai_layers.agent_task_helpers import clear_agent_task_active

            clear_agent_task_active(conversation_id)
        payload = {"conversation_id": conversation_id, **event_data}
        notify_user(notification_route_id, "agent_loop_finished", payload)

    logger.info(
        "conversation_agent_task started: conversation=%s user=%s agents=%s tools=%s modality=%s",
        conversation_id, user_id, agent_slugs, tool_names, multiagentic_modality,
    )

    from api.consumption.actions import _check_org_subscription, notify_org_billing_denied
    from api.messaging.tasks import get_user_organization

    billing_org_id = conversation.organization_id
    if not billing_org_id and conversation.user_id:
        _org = get_user_organization(conversation.user)
        billing_org_id = _org.id if _org else None
    if billing_org_id is not None:
        allowed, billing_reason = _check_org_subscription(billing_org_id)
        if not allowed:
            notify_uid = conversation.user_id or actor_user_id or notification_route_id
            notify_org_billing_denied(notify_uid, billing_reason)
            emit_finished(
                {
                    "output": "",
                    "message_id": None,
                    "versions": [],
                    "attachments": [],
                    "iterations": 0,
                    "tool_calls_count": 0,
                    "status": "error",
                    "error": "organization_billing_blocked",
                    "billing_reason": billing_reason,
                }
            )
            return {
                "status": "error",
                "error": "organization_billing_blocked",
                "billing_reason": billing_reason,
            }

    agent_sessions_created = []
    agent_event_log: list[dict] = []
    _is_handoff_continuation = (
        isinstance(user_message_metadata, dict)
        and user_message_metadata.get("source") == "agent_handoff"
    )
    try:
        meta_update = (
            dict(user_message_metadata)
            if isinstance(user_message_metadata, dict)
            and user_message_metadata
            and not _is_handoff_continuation
            else None
        )
        if skip_persist_user_message:
            if not existing_user_message_id:
                emit_event("error", {"error": "existing_user_message_id required for handoff"})
                from api.ai_layers.agent_task_helpers import clear_agent_task_active

                clear_agent_task_active(conversation_id)
                return {
                    "status": "error",
                    "error": "existing_user_message_id required for handoff",
                }
            try:
                user_message = Message.objects.get(
                    id=existing_user_message_id,
                    conversation=conversation,
                    type="user",
                )
            except Message.DoesNotExist:
                emit_event("error", {"error": "User message for handoff not found"})
                from api.ai_layers.agent_task_helpers import clear_agent_task_active

                clear_agent_task_active(conversation_id)
                return {"status": "error", "error": "User message for handoff not found"}
            message_attachments = list(user_message.attachments or [])
        elif regenerate_message_id:
            try:
                user_message = Message.objects.get(
                    id=regenerate_message_id,
                    conversation=conversation,
                    type="user",
                )
                user_message.text = user_message_text
                user_message.attachments = message_attachments
                update_fields = ["text", "attachments"]
                if meta_update:
                    merged = dict(user_message.metadata or {})
                    merged.update(meta_update)
                    user_message.metadata = merged
                    update_fields.append("metadata")
                user_message.save(update_fields=update_fields)
                Message.objects.filter(
                    conversation=conversation,
                    id__gt=user_message.id,
                ).delete()
            except Message.DoesNotExist:
                emit_event("error", {"error": "Message to regenerate not found"})
                from api.ai_layers.agent_task_helpers import clear_agent_task_active

                clear_agent_task_active(conversation_id)
                return {"status": "error", "error": "Message to regenerate not found"}
        else:
            try:
                create_kwargs = dict(
                    conversation=conversation,
                    type="user",
                    text=user_message_text,
                    attachments=message_attachments,
                )
                if meta_update:
                    create_kwargs["metadata"] = meta_update
                user_message = Message.objects.create(**create_kwargs)
                for att in attachment_objects:
                    att.message = user_message
                    att.save(update_fields=["message"])
            except Exception:
                emit_event("error", {"error": "Failed to save user message"})
                from api.ai_layers.agent_task_helpers import clear_agent_task_active

                clear_agent_task_active(conversation_id)
                return {"status": "error", "error": "Failed to save user message"}

        agents_by_slug = {
            a.slug: a
            for a in Agent.objects.filter(slug__in=agent_slugs).select_related(
                "organization",
                "llm",
                "llm__provider",
            )
        }
        agents_ordered = [agents_by_slug[s] for s in agent_slugs if s in agents_by_slug]
        if not agents_ordered:
            emit_event("error", {"error": "No valid agents found"})
            from api.ai_layers.agent_task_helpers import clear_agent_task_active

            clear_agent_task_active(conversation_id)
            return {"status": "error", "error": "No valid agents found"}

        versions = []
        total_iterations = 0
        total_tool_calls = 0
        assistant_message_attachments: list[dict] = []
        assistant_attachment_ids: list[str] = []
        primary_text = ""
        assistant_message_id = None
        task_return_attachments: list[dict] = []

        prev_messages = _serialize_prev_messages(
            conversation,
            user_message.id,
            user_id=actor_user_id or conversation.user_id,
        )
        loop_current_user_text = user_message_text
        loop_current_attachments = message_attachments
        tag_other_agent_versions = False
        if _is_handoff_continuation:
            prev_messages = list(prev_messages)
            prev_messages.append(
                {
                    "id": user_message.id,
                    "type": "user",
                    "text": user_message.text,
                    "versions": user_message.versions or [],
                    "attachments": user_message.attachments or [],
                }
            )
            later_msgs = Message.objects.filter(
                conversation=conversation,
                id__gt=user_message.id,
            ).order_by("id")
            for m in later_msgs:
                prev_messages.append(
                    {
                        "id": m.id,
                        "type": m.type,
                        "text": m.text,
                        "versions": m.versions or [],
                        "attachments": m.attachments or [],
                    }
                )
            loop_current_user_text = (
                "Continue from the agent handoff. "
                "Follow the AGENT HANDOFF block in your instructions."
            )
            loop_current_attachments = []
            tag_other_agent_versions = True

        attachment_ids = [
            inp.get("attachment_id") or inp.get("id")
            for inp in resolved_inputs
            if inp.get("type") == "input_attachment"
        ]
        attachment_ids_instruction = ""
        if attachment_ids:
            attachment_ids_instruction = (
                "\n\nThe user has attached items. Read them with the read_attachment tool. "
                "Available attachment IDs: " + ", ".join(str(aid) for aid in attachment_ids if aid) + "\n"
                "When referencing attachments in markdown:\n"
                "- Use ![Alt text](attachment:<attachment_id>) ONLY for image attachments.\n"
                "- For documents/audio/other files, use [Label](attachment:<attachment_id>) instead.\n"
            )

        from api.authenticate.models import UserProfile

        user_profile_text = ""
        if actor_user_id:
            try:
                user_profile_text = UserProfile.objects.get(
                    user_id=actor_user_id
                ).get_as_text()
            except UserProfile.DoesNotExist:
                pass

        from api.authenticate.services import FeatureFlagService
        from django.contrib.auth.models import User as DjangoUser

        def _organization_for_conversations_dashboard_flag(conv):
            org = getattr(conv, "organization", None)
            if org:
                return org
            if getattr(conv, "user", None):
                from api.messaging.tasks import get_user_organization

                return get_user_organization(conv.user)
            if getattr(conv, "chat_widget", None):
                w = conv.chat_widget
                agent = getattr(w, "agent", None) if w else None
                if agent:
                    return getattr(agent, "organization", None)
            if getattr(conv, "ws_number", None):
                agent = getattr(conv.ws_number, "agent", None)
                if agent:
                    return getattr(agent, "organization", None)
            return None

        _flag_org = _organization_for_conversations_dashboard_flag(conversation)
        has_organization_conversations_access = False
        _may_eval_org_dashboard = not is_widget_chat and (
            not is_whatsapp_chat or actor_user_id is not None
        )
        if _may_eval_org_dashboard and _flag_org is not None and actor_user_id is not None:
            try:
                _flag_user = DjangoUser.objects.get(pk=actor_user_id)
                has_organization_conversations_access, _ = (
                    FeatureFlagService.is_feature_enabled(
                        "conversations-dashboard",
                        organization=_flag_org,
                        user=_flag_user,
                    )
                )
            except DjangoUser.DoesNotExist:
                pass
        logger.info(
            "conversation_agent_task: has_organization_conversations_access=%s org_id=%s",
            has_organization_conversations_access,
            getattr(_flag_org, "id", None),
        )

        clock_context = _agent_clock_context(
            client_datetime,
            organization_id=getattr(_flag_org, "id", None),
        )

        for index, agent in enumerate(agents_ordered):
            instructions = agent.format_prompt()
            llm = agent.llm
            model_slug = llm.slug if llm else (agent.model_slug or "gpt-5.2")

            if tool_names_by_agent is not None:
                agent_tool_names = list(tool_names_by_agent.get(agent.slug) or [])
            elif tool_names:
                agent_tool_names = list(tool_names)
            else:
                agent_tool_names = list(agent.pre_approved_tools or [])

            if not is_embedded_channel and actor_user_id is not None:
                from api.ai_layers.tools import CHAT_REQUIRED_TOOL_NAMES

                for _req in CHAT_REQUIRED_TOOL_NAMES:
                    if _req not in agent_tool_names and _may_auto_inject_tool(_req):
                        agent_tool_names.append(_req)

            instructions += f"\n\nYour name is: {agent.name}."
            instructions += f"\n{clock_context}"
            if user_profile_text:
                instructions += f"\n{user_profile_text}"

            if attachment_ids_instruction:
                instructions = instructions + attachment_ids_instruction

            if "rag_query" in (agent_tool_names or []):
                instructions += (
                    "\n\nRAG (agent trained-memory search) is available via rag_query. "
                    "Call it when the user's message would benefit from facts stored as approved "
                    "completions in this agent's vector memory that may not be in the chat already. "
                    "Skip it for small talk, meta requests, or when the thread already contains enough "
                    "context. Pass a small list of queries (1-5) derived from the user's request. "
                    "If rag_query returns no results, mention that briefly if relevant, then answer from "
                    "general knowledge or the conversation. "
                    "rag_query does not list uploaded knowledge-base files — use "
                    "list_knowledge_base_documents / read_knowledge_base_document for those when enabled."
                )
            if "list_knowledge_base_documents" in (agent_tool_names or []) or (
                "read_knowledge_base_document" in (agent_tool_names or [])
            ):
                instructions += (
                    "\n\nKnowledge-base document tools are available. "
                    "Use list_knowledge_base_documents to discover uploaded documents the user can "
                    "access (personal, organization, or role-scoped), including briefs, tokens, and "
                    "belongs_to. Use read_knowledge_base_document with a document id to load full text. "
                    "Prefer listing first when you need to choose among documents. "
                    "These tools are separate from rag_query (trained agent memory)."
                )
            if "explore_web" in (agent_tool_names or []):
                instructions += (
                    "\n\nWeb search is available. "
                    "Call explore_web when fresh, external, or time-sensitive information would materially "
                    "improve the answer (news, live data, URLs, facts you're unsure about). "
                    "Skip it when a web lookup is unnecessary (e.g. opinion, creative writing, or the "
                    "answer is already established in the thread). "
                    "If explore_web returns no useful results, say so briefly if it matters, then continue."
                )
            if "create_image" in (agent_tool_names or []):
                from api.ai_layers.tools.create_image import (
                    image_models_agent_instructions_snippet,
                )

                instructions += (
                    "\n\nImage generation is enabled for this conversation. "
                    f"{image_models_agent_instructions_snippet()}"
                )
            if "generate_video" in (agent_tool_names or []):
                instructions += (
                    "\n\nVideo generation is enabled using Google Veo 3.1. "
                    "Call generate_video(prompt, image_attachment_id, aspect_ratio) when the user asks for a video. "
                    "prompt is always required — describe the motion, camera movement, and scene. "
                    "aspect_ratio for video must be landscape or portrait only (16:9 or 9:16 — Veo does not support square; default landscape). "
                    "image_attachment_id is OPTIONAL — provide it only when the user has an existing image in the conversation they want animated as the first frame. "
                    "If no image is available or the user just wants text-to-video, leave image_attachment_id empty. "
                    "Do NOT ask the user to provide an image before generating — just call the tool with the prompt alone if no image is available. "
                    "Video generation takes up to 6 minutes — inform the user it may take a moment. "
                    "\n\nWhen referencing the video attachment in markdown, link it like: "
                    "![Video](attachment:<attachment_id>)."
                )
            _doc_tools_ok = (
                override_allowlist is None
                or "generate_document_file" in (agent_tool_names or [])
            )
            _excel_tools_ok = (
                override_allowlist is None
                or "generate_excel_file" in (agent_tool_names or [])
            )
            if _doc_tools_ok:
                instructions += (
                    "\n\nDocument file generation is enabled (generate_document_file). "
                    "When the user wants a downloadable Word document created from scratch "
                    "(report, letter, resume, proposal, etc.) and you are NOT using an "
                    "assigned Word template, call generate_document_file(document_string, extension, output_filename). "
                    "- document_string: the full document body (markdown or HTML). "
                    "- extension: 'md' for markdown or 'html' for HTML. "
                    "- output_filename: optional .docx filename (default document.docx). "
                    "Output is always DOCX. "
                    "After success, include: [Download document](attachment:<attachment_id>)."
                )
            if _excel_tools_ok:
                instructions += (
                    "\n\nExcel file generation is enabled (generate_excel_file). "
                    "When the user wants a downloadable spreadsheet (tables, budgets, "
                    "lists, exports, etc.), call generate_excel_file(sheets_json, output_filename). "
                    "- sheets_json: JSON array of sheet objects with name, optional headers, and rows. "
                    "Example: "
                    '[{"name":"Sales","headers":["Month","Revenue"],"rows":[["Jan",1000],["Feb",1200]]}]. '
                    "- output_filename: optional .xlsx filename (default spreadsheet.xlsx). "
                    "Output is always XLSX. "
                    "After success, include: [Download spreadsheet](attachment:<attachment_id>)."
                )
            if (
                "generate_gamma_attachment" in (agent_tool_names or [])
                or "generate_gamma_presentation" in (agent_tool_names or [])
            ):
                instructions += (
                    "\n\nGamma file generation is enabled (generate_gamma_attachment). "
                    "When the user wants a downloadable slide deck or a designed document, "
                    "call generate_gamma_attachment(input_text, orientation, title, num_cards, "
                    "text_mode, language, additional_instructions, export_format, "
                    "output_filename). "
                    "- orientation: 'horizontal' for landscape 16:9 slides, 'vertical' "
                    "for a portrait A4 document/PDF. "
                    "- input_text: topic or outline (required). "
                    "- export_format: default 'pdf' for sharing; use 'pptx' only if the user "
                    "needs an editable PowerPoint (horizontal). "
                    "Generation can take up to a few minutes — tell the user it may take a moment. "
                    "After success, include: [Download file](attachment:<attachment_id>)."
                )
            if "create_speech" in (agent_tool_names or []):
                from api.voices.instructions import build_create_speech_tool_instructions

                instructions += build_create_speech_tool_instructions()
            if "generate_dialogue" in (agent_tool_names or []):
                from api.voices.instructions import build_generate_dialogue_tool_instructions

                instructions += build_generate_dialogue_tool_instructions()
            if "create_completion" in (agent_tool_names or []):
                instructions += (
                    "\n\n=== INTERACTIVE TRAINING (create_completion) ===\n"
                    "This tool saves training rows for the agent (pending approval; later retrievable via RAG when enabled).\n"
                    "Field semantics (important — do NOT treat this as \"fake user message + reply\" only):\n"
                    "- prompt: a CUE / hint for WHEN this completion applies. Describe the situation, topic, intent, or "
                    "phrasing that should trigger it (keywords, scenario, user goal). It does NOT have to be a verbatim "
                    "user chat message; it is the retrieval/matching side — what this row is \"about\".\n"
                    "- answer: the PAYLOAD for that cue — the information to memorize or apply: preferred reply wording, "
                    "facts, procedures, tone, required opening line, step-by-step, etc. Put the teachable content HERE.\n"
                    "Keep both fields concrete and self-contained. Avoid empty meta in answer (e.g. only \"understood\"); "
                    "the answer should carry the substance the user wanted stored.\n"
                    "Call create_completion only when the user clearly teaches, corrects, or asks to persist knowledge.\n"
                    "After each successful call, include: [Edit training example](completion:<completion_id>) with the returned integer id.\n"
                    "=== END INTERACTIVE TRAINING ===\n"
                )

            if multiagentic_modality == "grupal":
                grupal_preamble = (
                    "\n\n=== GROUP CONVERSATION ===\n"
                    "You are participating in a GROUP CHAT alongside other AI assistants. "
                    "Each assistant takes turns responding to the same user message. "
                    "You can see the other assistants' responses in the conversation history — "
                    "they are real participants in this chat, not text pasted by the user. "
                    "Treat them as fellow participants: you can agree, disagree, add to, "
                    "or complement their responses. Do NOT repeat what they already said. "
                    "Give ONLY your own response — do not summarize or restate theirs.\n"
                    "=== END GROUP CONVERSATION ===\n"
                )
                if versions:
                    grupal_preamble += "\nResponses from other assistants so far:\n"
                    for v in versions:
                        grupal_preamble += f"\n--- {v.get('agent_name', 'Unknown')} ---\n{v.get('text', '')}\n"
                instructions = instructions + grupal_preamble

            organization = (
                getattr(conversation, "organization", None)
                or getattr(agent, "organization", None)
            )
            if not organization and getattr(conversation, "user", None):
                from api.messaging.tasks import get_user_organization

                organization = get_user_organization(conversation.user)
            if not organization and getattr(conversation, "chat_widget", None):
                widget_agent = getattr(conversation.chat_widget, "agent", None)
                if widget_agent:
                    organization = getattr(widget_agent, "organization", None)

            from api.ai_layers.tools import WHATSAPP_TEMPLATE_AGENT_TOOL_NAMES
            from api.ai_layers.tools.calendar_tool_helpers import CALENDAR_AGENT_TOOL_NAMES
            from api.integrations.services import user_has_personal_google_calendar
            from api.whatsapp.models import WSNumber

            _has_personal_calendar = user_has_personal_google_calendar(actor_user_id)
            agent_tool_names = [
                t for t in agent_tool_names if t not in CALENDAR_AGENT_TOOL_NAMES
            ]
            if (
                _has_personal_calendar
                and not is_embedded_channel
                and actor_user_id is not None
            ):
                for _cal_tool in CALENDAR_AGENT_TOOL_NAMES:
                    if _cal_tool not in agent_tool_names and _may_auto_inject_tool(_cal_tool):
                        agent_tool_names.append(_cal_tool)

            _wa_line_qs = WSNumber.objects.filter(agent_id=agent.id).exclude(
                platform_id__isnull=True
            ).exclude(platform_id="")
            if organization is not None:
                _wa_line_qs = _wa_line_qs.filter(organization=organization)
            _agent_has_whatsapp_line = _wa_line_qs.exists()
            if not _agent_has_whatsapp_line:
                agent_tool_names = [
                    t
                    for t in agent_tool_names
                    if t not in WHATSAPP_TEMPLATE_AGENT_TOOL_NAMES
                ]

            if is_widget_chat:
                from api.ai_layers.tools import WIDGET_UNAVAILABLE_TOOL_NAMES

                agent_tool_names = [
                    t
                    for t in agent_tool_names
                    if t not in WIDGET_UNAVAILABLE_TOOL_NAMES
                ]
            if is_whatsapp_chat:
                agent_tool_names = [
                    t
                    for t in agent_tool_names
                    if t not in ("list_agents", "handoff_to_agent")
                ]
            applicable_alert_rules = []
            if organization:
                from api.messaging.models import ConversationAlertRule, ConversationAlert

                rules_qs = ConversationAlertRule.objects.filter(
                    organization=organization,
                    enabled=True,
                ).prefetch_related("agents")
                for rule in rules_qs:
                    if rule.scope == "all_conversations":
                        applicable_alert_rules.append(rule)
                    elif rule.scope == "selected_agents" and agent in rule.agents.all():
                        applicable_alert_rules.append(rule)

            logger.debug(
                "Alert rules check: conv_org=%s agent_org=%s applicable=%d",
                getattr(conversation, "organization_id", None),
                getattr(agent, "organization_id", None),
                len(applicable_alert_rules),
            )
            if applicable_alert_rules and not is_whatsapp_chat:
                rules_info = [
                    {"id": str(r.id), "name": r.name, "trigger": r.trigger}
                    for r in applicable_alert_rules
                ]
                import json as _json
                rules_json = _json.dumps(rules_info, ensure_ascii=False, indent=2)
                existing_alerts = list(
                    conversation.alerts.values(
                        "id", "alert_rule_id", "status", "reasoning", "extractions", "title"
                    )
                )
                existing_list = [
                    {
                        "id": str(a["id"]),
                        "alert_rule_id": str(a["alert_rule_id"]),
                        "status": a["status"],
                        "title": a["title"],
                        "extractions": [
                            {"key": k, "value": str(v)}
                            for k, v in (a["extractions"] or {}).items()
                        ],
                    }
                    for a in existing_alerts
                ]
                existing_json = _json.dumps(existing_list, ensure_ascii=False, indent=2)
                instructions += (
                    f"\n\n=== ALERT RULES ===\n"
                    f"You have access to the raise_alert tool.\n"
                    f"- CREATE: call with alert_rule_id, reasoning, and extractions. "
                    f"Always populate extractions with structured data (names, dates, amounts, phone, room_type, etc.). "
                    f"Example: extractions=[{{\"key\":\"room_type\",\"value\":\"Single\"}},{{\"key\":\"phone\",\"value\":\"0964105554\"}},{{\"key\":\"nights\",\"value\":\"2\"}}]\n"
                    f"- UPDATE: when the user adds more info, use alert_id, reasoning, title (if needed), and extractions. "
                    f"You MUST pass extractions when updating — include ALL known fields (old + new) as key/value pairs. "
                    f"NEVER pass extractions as null or empty when there is data in the conversation.\n"
                    f"Do NOT raise alerts for rules that do not match.\n\n"
                    f"RULES:\n{rules_json}\n\n"
                    f"ALREADY RAISED (id=alert_id for updates):\n{existing_json}\n"
                    f"=== END ALERT RULES ===\n"
                )
                if "raise_alert" not in agent_tool_names and _may_auto_inject_tool("raise_alert"):
                    agent_tool_names.append("raise_alert")
            else:
                if "raise_alert" in agent_tool_names:
                    agent_tool_names.remove("raise_alert")

            if not is_embedded_channel:
                if (
                    "read_plugin_instructions" not in agent_tool_names
                    and _may_auto_inject_tool("read_plugin_instructions")
                ):
                    agent_tool_names.append("read_plugin_instructions")

            tagging_tools = (
                "query_organization_tags",
                "create_organization_tag",
                "change_conversation_tags",
            )
            _wa_cross_thread = frozenset(
                {"get_tag_context", "query_conversation", "list_conversations"}
            )
            is_linked_whatsapp_actor = is_whatsapp_chat and actor_user_id is not None
            supports_web_org_tagging = organization and not is_embedded_channel
            supports_whatsapp_org_tagging = (
                organization
                and is_whatsapp_chat
                and bool(_wa_cross_thread.intersection(agent_tool_names))
            )
            supports_same_user_conversation_tools = (
                organization
                and actor_user_id is not None
                and (supports_web_org_tagging or is_linked_whatsapp_actor)
            )
            if (
                supports_web_org_tagging
                or supports_whatsapp_org_tagging
                or supports_same_user_conversation_tools
            ):
                conversation.refresh_from_db(fields=["tags", "summary"])
                tags_preamble = _conversation_tags_instruction_block(
                    conversation, organization.id
                )
                if supports_web_org_tagging or is_linked_whatsapp_actor:
                    if supports_web_org_tagging:
                        for _tn in tagging_tools:
                            if _tn not in agent_tool_names and _may_auto_inject_tool(_tn):
                                agent_tool_names.append(_tn)
                    if actor_user_id is not None:
                        if (
                            "get_tag_context" not in agent_tool_names
                            and _may_auto_inject_tool("get_tag_context")
                        ):
                            agent_tool_names.append("get_tag_context")
                        if (
                            "query_conversation" not in agent_tool_names
                            and _may_auto_inject_tool("query_conversation")
                        ):
                            agent_tool_names.append("query_conversation")
                        if (
                            "list_conversations" not in agent_tool_names
                            and _may_auto_inject_tool("list_conversations")
                        ):
                            agent_tool_names.append("list_conversations")
                    if supports_web_org_tagging and (
                        "change_conversation_summary" not in agent_tool_names
                        and _may_auto_inject_tool("change_conversation_summary")
                    ):
                        agent_tool_names.append("change_conversation_summary")
                tag_tools_intro = (
                    "Tagging tools are always enabled for this organization on every turn.\n"
                    if supports_web_org_tagging
                    else "Tag and cross-thread tools are enabled on this WhatsApp line.\n"
                )
                if (
                    supports_whatsapp_org_tagging
                    or "change_conversation_summary" in agent_tool_names
                ):
                    summary_preamble = _conversation_summary_instruction_block(conversation)
                    instructions += (
                        "\n\n=== CONVERSATION SUMMARY ===\n"
                        f"{summary_preamble}"
                        "=== END CONVERSATION SUMMARY ===\n"
                    )
                instructions += (
                    "\n\n=== CONVERSATION TAGS ===\n"
                    f"{tags_preamble}"
                    f"{tag_tools_intro}"
                    "You already have this conversation’s tag ids and titles above — do **not** call "
                    "query_organization_tags unless you truly need the full organization catalog "
                    "(for example after creating a new tag, or when comparing many similar labels).\n\n"
                    "Tools:\n"
                    "- query_organization_tags: optional; full list of enabled tags for the org.\n"
                    "- create_organization_tag: when no suitable tag exists yet (short, unique title).\n"
                    "- change_conversation_tags: set exactly 1–3 tag ids for this conversation (replaces the whole set). "
                    "Do not use this to clear tags unless the user explicitly asks to remove all labels.\n"
                )
                if supports_same_user_conversation_tools:
                    if has_organization_conversations_access:
                        instructions += (
                            "- **Org-wide thread visibility:** this user has the same conversation visibility as the "
                            "organization dashboard — `list_conversations` / `get_tag_context` may include teammates’ "
                            "threads, and `query_conversation` may read those threads when you have a `conversation_id`.\n"
                        )
                    instructions += (
                        "- list_conversations: list **active** conversations this user can access (app + linked "
                        "WhatsApp). Use when you need to find another thread for the same person; each row has "
                        "conversation_id, title, summary, channel, is_current. Then call `query_conversation`.\n"
                        "- get_tag_context: **How to call** — use the tool name `get_tag_context` with argument "
                        "`tag_id` set to the **integer id** of the tag (the number shown as tag_id=… above or from "
                        "`query_organization_tags`), e.g. tag_id=14. Do **not** pass the tag’s text title as tag_id.\n"
                        "  **When to call:** if the user’s message is substantive and you are **about to reuse** or "
                        "**already using** a tag that could tie this chat to earlier work (same product, codebase, "
                        "client, or project), call `get_tag_context` for that **one** tag_id **before** your main answer "
                        "so you can reuse vocabulary, avoid re-asking setup questions, or stay consistent with past summaries. "
                        "If you are choosing among several tags, you may call once for the best-matching tag_id.\n"
                        "  **When not to call:** greetings, unrelated small talk, or when no tag clearly applies.\n"
                        "  **Response:** each row has conversation title, summary, n_messages, date — use only as hints; "
                        "empty list means no other threads with that tag"
                        + (" in the organization" if has_organization_conversations_access else " for this user")
                        + ".\n"
                        "- query_conversation: pass `conversation_id` (UUID of **which** thread to read) and `question` "
                        "(a precise question). A **separate small model** reads up to a few hundred messages from that "
                        "thread and returns **only a distilled answer** — not the raw logs — so you can answer things like "
                        "“what did I tell you last week about X?” without overloading context. Use **after** you know "
                        "which `conversation_id` matters (often from `list_conversations` or `get_tag_context`). "
                        "Do not spam it every turn.\n"
                    )
                elif supports_whatsapp_org_tagging:
                    if "get_tag_context" in agent_tool_names:
                        instructions += (
                            "- get_tag_context: pass `tag_id` as the **integer id** (not the title). Lists other "
                            "threads **across the organization** with that tag (title, summary, n_messages, date). "
                            "Call before reusing a topic when a tag applies.\n"
                        )
                    if "query_conversation" in agent_tool_names:
                        instructions += (
                            "- query_conversation: pass `conversation_id` (from get_tag_context) and `question`. "
                            "Returns a distilled answer from that thread’s messages (any org conversation you have an id for). "
                            "Use after you know which conversation_id matters.\n"
                        )
                instructions += (
                    "\n"
                    "Rules:\n"
                    "- If the conversation still **needs tags** (see state above) and the user’s latest message "
                    "has enough substance to infer topic, intent, product, or problem area — you **must** "
                    "finish with change_conversation_tags assigning **at least 1** and **at most 3** valid tag ids "
                    "(create_organization_tag first if needed). Pure greetings, empty input, or purely meta "
                    "requests with no topic yet: wait for a substantive message before assigning.\n"
                    "- If the conversation **has tags**, keep them unless the new message clearly warrants different labels.\n"
                    "=== END CONVERSATION TAGS ===\n"
                )

            if not is_embedded_channel:
                instructions += format_available_plugins_summary()

            from api.document_templates.context import (
                agent_has_template_assignments,
                format_assigned_templates_instruction,
            )

            if agent_has_template_assignments(agent):
                instructions += format_assigned_templates_instruction(agent)
                for _tpl_tool in ("list_document_templates", "render_document_template"):
                    if _tpl_tool not in agent_tool_names and _may_auto_inject_tool(_tpl_tool):
                        agent_tool_names.append(_tpl_tool)

            if (
                "generate_document_file" not in agent_tool_names
                and _may_auto_inject_tool("generate_document_file")
            ):
                agent_tool_names.append("generate_document_file")
            if (
                "generate_excel_file" not in agent_tool_names
                and _may_auto_inject_tool("generate_excel_file")
            ):
                agent_tool_names.append("generate_excel_file")

            if (
                not is_embedded_channel
                and actor_user_id is not None
                and organization is not None
            ):
                _actor_has_email = False
                try:
                    _actor_user = DjangoUser.objects.get(pk=actor_user_id)
                    _actor_has_email = bool((_actor_user.email or "").strip())
                except DjangoUser.DoesNotExist:
                    _actor_has_email = False
                if _actor_has_email:
                    for _email_tool in (
                        "send_email",
                        "list_organization_members",
                        "list_organization_roles",
                    ):
                        if (
                            _email_tool not in agent_tool_names
                            and _may_auto_inject_tool(_email_tool)
                        ):
                            agent_tool_names.append(_email_tool)

                from api.ai_layers.tools import SCHEDULE_AGENT_TOOL_NAMES

                _wa_tpl_injected = False
                if _agent_has_whatsapp_line:
                    for _wa_tool in WHATSAPP_TEMPLATE_AGENT_TOOL_NAMES:
                        if (
                            _wa_tool not in agent_tool_names
                            and _may_auto_inject_tool(_wa_tool)
                        ):
                            agent_tool_names.append(_wa_tool)
                            _wa_tpl_injected = True
                    if _wa_tpl_injected or any(
                        t in agent_tool_names
                        for t in WHATSAPP_TEMPLATE_AGENT_TOOL_NAMES
                    ):
                        instructions += (
                            "\n\nYou can notify organization members on WhatsApp with approved "
                            "templates, using only WhatsApp lines assigned to you. "
                            "Use list_whatsapp_resources (your lines with verified "
                            "contacts), list_whatsapp_templates, then send_ws_template_message "
                            "with sender_id and ws_contact_id. A member may have multiple "
                            "verified contacts (phones); pick the exact ws_contact_id."
                        )

                _schedule_injected = False
                for _sched_tool in SCHEDULE_AGENT_TOOL_NAMES:
                    if (
                        _sched_tool not in agent_tool_names
                        and _may_auto_inject_tool(_sched_tool)
                    ):
                        agent_tool_names.append(_sched_tool)
                        _schedule_injected = True
                if _schedule_injected or any(
                    t in agent_tool_names for t in SCHEDULE_AGENT_TOOL_NAMES
                ):
                    from api.ai_layers.tools.calendar_tool_helpers import (
                        resolve_org_timezone,
                    )

                    _sched_tz = resolve_org_timezone(organization.id)
                    instructions += (
                        "\n\nYou can schedule future agent work in this conversation with "
                        "schedule_task (one-off or recurring). "
                        "When calling schedule_task: provide a short title, and write instruction "
                        "as a numbered step-by-step execution plan (which tools/actions to use and "
                        "in what order) — not as a natural-language user request to schedule work. "
                        "Omit agent_slugs to keep the agents currently selected in this chat; "
                        "pass agent_slugs to choose who participates — you may keep the current "
                        "agents and add more accessible specialists (use list_agents when available). "
                        "Each agent runs with its own pre_approved_tools at fire time "
                        "(no shared tools allowlist on the schedule). "
                        "That plan will be injected later as an automatic scheduled-execution message. "
                        f"Organization timezone for task scheduling: {_sched_tz}. "
                        "Use list_scheduled_tasks and cancel_scheduled_task to manage schedules."
                    )

            _is_scheduled_run = (
                isinstance(user_message_metadata, dict)
                and user_message_metadata.get("source") == "scheduled_task"
            )
            if _is_scheduled_run:
                from api.ai_layers.tools import SCHEDULE_AGENT_TOOL_NAMES

                agent_tool_names = [
                    t
                    for t in agent_tool_names
                    if t not in SCHEDULE_AGENT_TOOL_NAMES
                ]
                _sched_title = user_message_metadata.get("scheduled_task_title") or ""
                _sched_kind = user_message_metadata.get("scheduled_task_kind") or "scheduled"
                _sched_id = user_message_metadata.get("scheduled_task_id") or ""
                _sched_plan = (
                    user_message_metadata.get("scheduled_task_plan") or ""
                ).strip()
                instructions += (
                    "\n\n=== SCHEDULED TASK RUN ===\n"
                    f"This turn is an automatic {_sched_kind} scheduled-task execution "
                    "for this conversation (not a live interactive user request). "
                    f"Title: {_sched_title or '(untitled)'}. "
                    f"Task ID: {_sched_id}. "
                    "Scheduling tools are unavailable on this turn — do not try to create, "
                    "list, or cancel schedules. "
                    "The user message shows only a short label; the full execution context "
                    "and step-by-step plan are inside the HTML comment in that message "
                    "(and repeated below). Follow that plan end-to-end. "
                    "Use the available tools to complete each step. "
                    "If a required capability is missing or fails, report that limitation "
                    "clearly and continue with what you can. "
                    "When finished, summarize what you completed and what remains blocked.\n"
                )
                if _sched_plan:
                    instructions += (
                        "\nStep-by-step execution plan:\n"
                        f"{_sched_plan}\n"
                    )
                instructions += "=== END SCHEDULED TASK RUN ==="

            if _is_handoff_continuation and isinstance(user_message_metadata, dict):
                _from_name = user_message_metadata.get("handoff_from_name") or "another agent"
                _from_slug = user_message_metadata.get("handoff_from_slug") or ""
                _handoff_instructions = (
                    user_message_metadata.get("handoff_agent_instructions")
                    or user_message_metadata.get("handoff_summary")
                    or ""
                ).strip()
                instructions += (
                    "\n\n=== AGENT HANDOFF ===\n"
                    "This turn continues work started by another assistant. "
                    f"From: {_from_name}"
                    + (f" ({_from_slug})" if _from_slug else "")
                    + ".\n"
                    "You are the specialist taking over. The conversation history includes "
                    "the user's request and the previous assistant's visible handoff message. "
                    "Follow the private instructions below; do not invent a second handoff.\n"
                )
                if _handoff_instructions:
                    instructions += (
                        f"\nInstructions from previous agent:\n{_handoff_instructions}\n"
                    )
                instructions += "=== END AGENT HANDOFF ===\n"

            if (
                not is_embedded_channel
                and "handoff_to_agent" in agent_tool_names
            ):
                instructions += (
                    "\n\n=== AGENT HANDOFF TOOLS ===\n"
                    "You can transfer this conversation to another specialist. "
                    "Use list_agents to see accessible agents (slug, name, description). "
                    "Then call handoff_to_agent with:\n"
                    "- agent_slug: target from list_agents\n"
                    "- message_for_user: required text shown to the user as YOUR assistant reply "
                    "(explain that you are handing off and why)\n"
                    "- agent_instructions: private instructions the next agent must follow "
                    "(what you did, what remains, why them) — never shown as a chat bubble\n"
                    "After a successful handoff, stop — do not continue working.\n"
                    "=== END AGENT HANDOFF TOOLS ===\n"
                )

            if any(t in agent_tool_names for t in CALENDAR_AGENT_TOOL_NAMES):
                instructions += (
                    "\n\nGoogle Calendar is connected for this user. "
                    "Use list_calendar_events to read schedules (today, this_week, next_week, last_week, day, custom). "
                    "Use create_calendar_event and update_calendar_event with start/end as YYYY-MM-DDTHH:MM:SS "
                    "in the organization timezone unless you include an offset. "
                    "Invite org members using guest_user_ids from list_organization_members (not raw emails)."
                )

            from api.finetuning.context_injection import (
                format_completions_context_block,
                get_completions_for_context,
            )

            auto_completions = get_completions_for_context(agent, conversation)
            auto_training_block = format_completions_context_block(auto_completions)
            if auto_training_block:
                instructions += auto_training_block

            model_ref = ModelRef(
                id=llm.id if llm else 0,
                slug=model_slug,
                provider=llm.provider.name if llm else "openai",
            )
            instructions += GENERAL_RULES
            inputs_data = AgentSessionInputs(
                instructions=instructions,
                user_inputs=resolved_inputs,
                user_message_text=user_message_text,
                tool_names=agent_tool_names,
                plugin_slugs=[],
                agent=AgentRef(id=agent.id, slug=agent.slug, name=agent.name),
                model=model_ref,
                multiagentic_modality=multiagentic_modality,
                prev_messages=prev_messages,
                max_iterations=max_iterations,
            ).model_dump()

            session = AgentSession.objects.create(
                conversation=conversation,
                user_message=user_message,
                task_type="chat_message",
                inputs=inputs_data,
                outputs={},
                agent_index=index,
            )
            agent_sessions_created.append(session)
            start_time = time.perf_counter()

            agent_event_log: list[dict] = []

            def on_event(event_type: str, event_data: dict) -> None:
                from django.utils import timezone as _tz

                agent_event_log.append(
                    {
                        "type": event_type,
                        "tool_name": event_data.get("tool_name"),
                        "iteration": event_data.get("iteration"),
                        "duration": event_data.get("duration"),
                        "error": event_data.get("error"),
                        "ts": _tz.now().isoformat(),
                    }
                )
                payload = {
                    "type": event_type,
                    "conversation_id": conversation_id,
                    "agent_slug": agent.slug,
                    "agent_name": agent.name,
                    **event_data,
                }
                notify_user(notification_route_id, "agent_events_channel", payload)

            def is_cancelled() -> bool:
                from django.core.cache import cache
                from api.messaging.takeover import is_takeover_active
                if cache.get(f"cancel_task_{conversation_id}"):
                    return True
                if is_takeover_active(conversation):
                    return True
                return AgentSession.objects.filter(id=session.id, dismissed_at__isnull=False).exists()

            handoff_request: dict = {}
            resolve_kwargs = dict(
                conversation_id=conversation_id,
                user_id=actor_user_id,
                agent_id=agent.id,
                agent_slug=agent.slug,
                current_agent_slug=agent.slug,
                organization_id=organization.id if organization else None,
                has_organization_conversations_access=has_organization_conversations_access,
                agent_slugs=agent_slugs,
                multiagentic_modality=multiagentic_modality,
                enabled_capabilities=list(agent_tool_names),
                handoff_request=handoff_request,
                is_whatsapp_chat=is_whatsapp_chat,
                chat_widget_id=getattr(conversation, "chat_widget_id", None),
            )
            if applicable_alert_rules and organization:
                resolve_kwargs["organization_id"] = organization.id
            if is_whatsapp_chat and actor_user_id is None:
                resolve_kwargs["is_whatsapp_visitor"] = True
                _strip_unlinked = {"list_conversations", *WHATSAPP_TEMPLATE_AGENT_TOOL_NAMES}
                agent_tool_names = [
                    n for n in agent_tool_names if n not in _strip_unlinked
                ]
            elif is_whatsapp_chat and actor_user_id is not None:
                if any(t in agent_tool_names for t in WHATSAPP_TEMPLATE_AGENT_TOOL_NAMES):
                    instructions += (
                        "\n\nYou can notify organization members on WhatsApp with approved "
                        "templates, using only WhatsApp lines assigned to you. "
                        "Use list_whatsapp_resources (your lines with verified "
                        "contacts), list_whatsapp_templates, then send_ws_template_message "
                        "with sender_id and ws_contact_id. A member may have multiple "
                        "verified contacts (phones); pick the exact ws_contact_id."
                    )

            tools = resolve_tools(agent_tool_names, **resolve_kwargs)

            loop = AgentLoop.create(
                provider=_agent_loop_provider_from_llm(llm),
                tools=tools,
                instructions=instructions,
                model=model_slug,
                max_iterations=max_iterations,
                on_event=on_event,
                check_cancelled=is_cancelled,
            )

            openai_inputs = _build_agent_loop_inputs(
                prev_messages=prev_messages,
                current_user_text=loop_current_user_text,
                current_user_attachments=loop_current_attachments,
                agent_slug=agent.slug,
                multiagentic_modality=multiagentic_modality,
                tag_other_agent_versions=tag_other_agent_versions,
            )
            
            try:
                from api.ai_layers.agent_loop import CancelledError
                agent_run_result = loop.run(openai_inputs)
            except CancelledError:
                logger.info("Task cancelled for conversation %s", conversation_id)
                from django.utils import timezone
                session.ended_at = timezone.now()
                session.event_log = agent_event_log
                session.save(update_fields=["ended_at", "event_log"])
                
                emit_event("agent_complete", {
                    "agent_slug": agent.slug,
                    "agent_name": agent.name,
                    "index": index + 1,
                    "total": len(agents_ordered),
                    "status": "cancelled"
                })
                emit_finished({
                    "output": "Generation stopped by user.",
                    "message_id": None,
                    "versions": [],
                    "attachments": [],
                    "iterations": total_iterations,
                    "tool_calls_count": total_tool_calls,
                    "next_agent_slug": None,
                    "status": "cancelled"
                })
                return {
                    "status": "cancelled",
                    "output": "Generation stopped by user.",
                    "message_id": None,
                    "versions": [],
                    "attachments": [],
                    "iterations": total_iterations,
                    "tool_calls_count": total_tool_calls,
                }

            from django.utils import timezone

            new_atts, new_ids = _extract_create_image_attachments(agent_run_result.tool_calls or [])
            if new_atts:
                assistant_message_attachments.extend(new_atts)
            if new_ids:
                assistant_attachment_ids.extend(new_ids)
 
            speech_atts, speech_ids = _extract_create_speech_attachments(agent_run_result.tool_calls or [])
            if speech_atts:
                assistant_message_attachments.extend(speech_atts)
            if speech_ids:
                assistant_attachment_ids.extend(speech_ids)

            dialogue_atts, dialogue_ids = _extract_generate_dialogue_attachments(
                agent_run_result.tool_calls or []
            )
            if dialogue_atts:
                assistant_message_attachments.extend(dialogue_atts)
            if dialogue_ids:
                assistant_attachment_ids.extend(dialogue_ids)

            video_atts, video_ids = _extract_generate_video_attachments(agent_run_result.tool_calls or [])
            if video_atts:
                assistant_message_attachments.extend(video_atts)
            if video_ids:
                assistant_attachment_ids.extend(video_ids)

            doc_atts, doc_ids = _extract_render_document_template_attachments(
                agent_run_result.tool_calls or []
            )
            if doc_atts:
                assistant_message_attachments.extend(doc_atts)
            if doc_ids:
                assistant_attachment_ids.extend(doc_ids)

            gen_doc_atts, gen_doc_ids = _extract_generate_document_file_attachments(
                agent_run_result.tool_calls or []
            )
            if gen_doc_atts:
                assistant_message_attachments.extend(gen_doc_atts)
            if gen_doc_ids:
                assistant_attachment_ids.extend(gen_doc_ids)

            gen_xlsx_atts, gen_xlsx_ids = _extract_generate_excel_file_attachments(
                agent_run_result.tool_calls or []
            )
            if gen_xlsx_atts:
                assistant_message_attachments.extend(gen_xlsx_atts)
            if gen_xlsx_ids:
                assistant_attachment_ids.extend(gen_xlsx_ids)

            gen_gamma_atts, gen_gamma_ids = (
                _extract_generate_gamma_attachment_attachments(
                    agent_run_result.tool_calls or []
                )
            )
            if gen_gamma_atts:
                assistant_message_attachments.extend(gen_gamma_atts)
            if gen_gamma_ids:
                assistant_attachment_ids.extend(gen_gamma_ids)

            if isinstance(agent_run_result.output, str):
                output_value = OutputValue(type="string", value=agent_run_result.output)
            elif hasattr(agent_run_result.output, "model_dump"):
                dump = agent_run_result.output.model_dump(mode="json")
                output_value = OutputValue(type="json", value=dump)
            else:
                output_value = OutputValue(type="string", value=str(agent_run_result.output))

            outputs_data = AgentSessionOutputs(
                messages=agent_run_result.messages,
                output=output_value,
                usage=agent_run_result.usage,
                status="completed",
                error=None,
            ).model_dump()

            session.outputs = outputs_data
            session.event_log = agent_event_log
            session.iterations = agent_run_result.iterations
            session.tool_calls_count = len(agent_run_result.tool_calls)
            session.ended_at = timezone.now()
            session.total_duration = time.perf_counter() - start_time
            session.save()

            import json as _json
            if isinstance(agent_run_result.output, str):
                output_text = agent_run_result.output
            elif hasattr(agent_run_result.output, "model_dump"):
                output_text = _json.dumps(agent_run_result.output.model_dump(), default=str)
            else:
                output_text = str(agent_run_result.output)

            referenced_atts = _extract_referenced_attachments_from_text(
                output_text,
                conversation_id=conversation_id,
            )
            if referenced_atts:
                existing_ids = {
                    str(a.get("attachment_id") or "")
                    for a in assistant_message_attachments
                }
                for att in referenced_atts:
                    aid = str(att.get("attachment_id") or "")
                    if aid and aid in existing_ids:
                        continue
                    assistant_message_attachments.append(att)
                    if aid:
                        existing_ids.add(aid)

            completion_atts_from_tools = _extract_create_completion_refs_from_tool_calls(
                agent_run_result.tool_calls or []
            )
            completion_atts_from_text = _extract_referenced_completions_from_text(
                output_text,
                getattr(conversation, "user", None),
            )
            existing_completion_ids = {
                str(a.get("completion_id") or a.get("id") or "")
                for a in assistant_message_attachments
                if str(a.get("type") or "") == "completion"
            }
            for att in completion_atts_from_tools + completion_atts_from_text:
                cid = str(att.get("completion_id") or att.get("id") or "")
                if cid and cid in existing_completion_ids:
                    continue
                assistant_message_attachments.append(att)
                if cid:
                    existing_completion_ids.add(cid)

            rag_sources = _extract_rag_sources(agent_run_result.tool_calls or [])

            version = {
                "agent_slug": agent.slug,
                "agent_name": agent.name,
                "type": "assistant",
                "sources": rag_sources,
                "usage": {
                    "prompt_tokens": agent_run_result.usage.get("prompt_tokens", 0),
                    "completion_tokens": agent_run_result.usage.get("completion_tokens", 0),
                    "total_tokens": agent_run_result.usage.get("total_tokens", 0),
                    "model_slug": model_slug,
                },
            }
            version["text"] = output_text
            versions.append(version)

            total_iterations += agent_run_result.iterations
            total_tool_calls += len(agent_run_result.tool_calls)

            emit_event("agent_version_ready", {"version": version})

            if handoff_request.get("requested"):
                from api.ai_layers.agent_task_helpers import mark_agent_task_active

                to_slug = handoff_request.get("to_agent_slug")
                to_name = handoff_request.get("to_agent_name") or to_slug
                handoff_user_message = (
                    handoff_request.get("message_for_user")
                    or handoff_request.get("user_message")
                    or output_text
                ).strip()
                handoff_agent_instructions = (
                    handoff_request.get("agent_instructions")
                    or handoff_request.get("summary")
                    or ""
                ).strip()
                version["text"] = handoff_user_message
                versions[-1] = version
                output_text = handoff_user_message

                try:
                    conv_ref = Conversation.objects.get(id=conversation_id)
                except Conversation.DoesNotExist:
                    logger.warning(
                        "Conversation %s not found (handoff save)", conversation_id
                    )
                    emit_finished(
                        {
                            "output": output_text,
                            "message_id": None,
                            "versions": [version],
                            "attachments": list(assistant_message_attachments),
                            "iterations": total_iterations,
                            "tool_calls_count": total_tool_calls,
                            "status": "error",
                            "error": "conversation_not_found",
                        }
                    )
                    return {
                        "status": "error",
                        "error": "conversation_not_found",
                    }

                handoff_msg = Message.objects.create(
                    conversation=conv_ref,
                    type="assistant",
                    text=handoff_user_message,
                    versions=[version],
                    attachments=assistant_message_attachments,
                    metadata={
                        "handoff": {
                            "to_slug": to_slug,
                            "to_name": to_name,
                            "from_slug": agent.slug,
                            "from_name": agent.name,
                        }
                    },
                )
                if assistant_attachment_ids:
                    from api.messaging.models import MessageAttachment

                    MessageAttachment.objects.filter(
                        conversation_id=conversation_id,
                        id__in=assistant_attachment_ids,
                    ).update(message=handoff_msg)
                session.assistant_message = handoff_msg
                session.save(update_fields=["assistant_message"])

                # Do not rewrite conversation.metadata.related_agents — the user's
                # chat selection must stay as they left it after a handoff.

                emit_event(
                    "agent_complete",
                    {
                        "agent_slug": agent.slug,
                        "agent_name": agent.name,
                        "index": index + 1,
                        "total": len(agents_ordered),
                        "handoff_to": to_slug,
                    },
                )
                emit_finished(
                    {
                        "output": handoff_user_message,
                        "message_id": handoff_msg.id,
                        "versions": [version],
                        "attachments": list(assistant_message_attachments),
                        "iterations": total_iterations,
                        "tool_calls_count": total_tool_calls,
                        "next_agent_slug": to_slug,
                        "handoff": True,
                    }
                )

                mark_agent_task_active(str(conversation_id))
                conversation_agent_task.delay(
                    conversation_id=str(conversation_id),
                    user_inputs=[
                        {
                            "type": "input_text",
                            "text": user_message.text or "",
                        }
                    ],
                    tool_names=[],
                    agent_slugs=[to_slug],
                    multiagentic_modality="isolated",
                    user_id=actor_user_id or notification_route_id,
                    client_datetime=client_datetime,
                    skip_persist_user_message=True,
                    existing_user_message_id=user_message.id,
                    user_message_metadata={
                        "source": "agent_handoff",
                        "handoff_from_slug": agent.slug,
                        "handoff_from_name": agent.name,
                        "handoff_agent_instructions": handoff_agent_instructions,
                    },
                )
                logger.info(
                    "conversation_agent_task handoff: conversation=%s from=%s to=%s",
                    conversation_id,
                    agent.slug,
                    to_slug,
                )
                return {
                    "status": "completed",
                    "output": handoff_user_message,
                    "iterations": total_iterations,
                    "tool_calls_count": total_tool_calls,
                    "message_id": handoff_msg.id,
                    "user_message_id": user_message.id,
                    "handoff_to": to_slug,
                    "attachments": list(assistant_message_attachments),
                }

            if multiagentic_modality == "grupal":
                try:
                    conv_ref = Conversation.objects.get(id=conversation_id)
                    grupal_msg = Message.objects.create(
                        conversation=conv_ref,
                        type="assistant",
                        text=output_text,
                        versions=[version],
                        attachments=assistant_message_attachments,
                    )
                    if assistant_attachment_ids:
                        from api.messaging.models import MessageAttachment
                        MessageAttachment.objects.filter(
                            conversation_id=conversation_id,
                            id__in=assistant_attachment_ids,
                        ).update(message=grupal_msg)
                    session.assistant_message = grupal_msg
                    session.save(update_fields=["assistant_message"])
                    attachments_for_notify = list(assistant_message_attachments)
                    assistant_message_attachments = []
                    assistant_attachment_ids = []

                    is_last_agent = index == len(agents_ordered) - 1
                    next_agent_slug = agents_ordered[index + 1].slug if not is_last_agent else None

                    emit_finished({
                        "output": output_text,
                        "message_id": grupal_msg.id,
                        "versions": [version],
                        "attachments": attachments_for_notify,
                        "iterations": total_iterations,
                        "tool_calls_count": total_tool_calls,
                        "next_agent_slug": next_agent_slug,
                    })
                except Conversation.DoesNotExist:
                    logger.warning("Conversation %s not found (grupal save)", conversation_id)

            emit_event("agent_complete", {
                "agent_slug": agent.slug,
                "agent_name": agent.name,
                "index": index + 1,
                "total": len(agents_ordered),
            })

        if multiagentic_modality != "grupal":
            assistant_message_id = None
            primary_text = versions[0]["text"] if versions else ""
            try:
                conversation = Conversation.objects.get(id=conversation_id)
                assistant_msg = Message.objects.create(
                    conversation=conversation,
                    type="assistant",
                    text=primary_text,
                    versions=versions,
                    attachments=assistant_message_attachments,
                )
                assistant_message_id = assistant_msg.id
                if assistant_attachment_ids:
                    from api.messaging.models import MessageAttachment

                    MessageAttachment.objects.filter(
                        conversation_id=conversation_id,
                        id__in=assistant_attachment_ids,
                    ).update(message=assistant_msg)
                for s in agent_sessions_created:
                    s.assistant_message = assistant_msg
                    s.save(update_fields=["assistant_message"])
                logger.info(
                    "conversation_agent_task generate_title after assistant message: "
                    "conversation_id=%s modality=isolated current_title=%r message_id=%s",
                    conversation_id,
                    conversation.title,
                    assistant_message_id,
                )
                conversation.generate_title()
            except Conversation.DoesNotExist:
                logger.warning(
                    "Conversation %s not found when saving assistant message",
                    conversation_id,
                )

            emit_finished({
                "output": primary_text,
                "message_id": assistant_message_id,
                "versions": versions,
                "attachments": list(assistant_message_attachments),
                "iterations": total_iterations,
                "tool_calls_count": total_tool_calls,
            })
            task_return_attachments = list(assistant_message_attachments)

        if multiagentic_modality == "grupal":
            try:
                conv = Conversation.objects.get(id=conversation_id)
                logger.info(
                    "conversation_agent_task generate_title (grupal): conversation_id=%s current_title=%r",
                    conversation_id,
                    conv.title,
                )
                conv.generate_title()
            except Conversation.DoesNotExist:
                logger.warning(
                    "conversation_agent_task generate_title skipped: conversation not found id=%s",
                    conversation_id,
                )

        logger.info(
            "conversation_agent_task completed: conversation=%s agents=%d iterations=%d tool_calls=%d",
            conversation_id, len(versions), total_iterations, total_tool_calls,
        )

        return {
            "status": "completed",
            "output": primary_text,
            "iterations": total_iterations,
            "tool_calls_count": total_tool_calls,
            "message_id": assistant_message_id,
            "user_message_id": user_message.id,
            "attachments": task_return_attachments,
        }

    except Exception as e:
        logger.error(
            "conversation_agent_task failed: conversation=%s error=%s",
            conversation_id, str(e),
        )
        emit_event("error", {"error": str(e)})

        if agent_sessions_created:
            from django.utils import timezone

            last_session = agent_sessions_created[-1]
            outputs_data = AgentSessionOutputs(
                messages=last_session.outputs.get("messages", []),
                output=OutputValue(type="string", value=""),
                usage=last_session.outputs.get("usage", {}),
                status="error",
                error=OutputError(message=str(e), traceback=tb.format_exc()),
            ).model_dump()
            last_session.outputs = outputs_data
            last_session.event_log = agent_event_log
            last_session.ended_at = timezone.now()
            last_session.tool_calls_count = sum(
                1 for m in last_session.outputs.get("messages", [])
                if m.get("type") == "function_call"
            )
            if last_session.started_at:
                last_session.total_duration = (
                    timezone.now() - last_session.started_at
                ).total_seconds()
            last_session.save(
                update_fields=["outputs", "event_log", "ended_at", "total_duration", "tool_calls_count"]
            )

        from api.ai_layers.agent_task_helpers import clear_agent_task_active

        clear_agent_task_active(conversation_id)
        return {"status": "error", "error": str(e)}

from api.ai_layers.platform_assistant_task import platform_assistant_task  # noqa: F401
from api.ai_layers.compliance_assistant_task import compliance_assistant_task  # noqa: F401
