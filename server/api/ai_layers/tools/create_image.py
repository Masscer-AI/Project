"""
Tool: create_image

Generates an image server-side and stores it as a MessageAttachment(kind="file"),
so it can be rendered in the frontend and later read via read_attachment().

This tool is only callable by the model when it's explicitly enabled via
AgentTask tool_names (see api/ai_layers/tools/TOOL_REGISTRY).
"""

from __future__ import annotations

import logging
import mimetypes
import base64
import os
import uuid
from typing import Literal

from django.core.files.base import ContentFile
from django.utils.text import slugify
from openai import OpenAI
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

AspectRatio = Literal["square", "landscape", "portrait"]

OPENAI_IMAGE_MODELS: set[str] = {"gpt-image-1.5"}
GOOGLE_IMAGE_MODELS: set[str] = {"gemini-3.1-flash-image-preview"}
ALL_IMAGE_MODELS: set[str] = OPENAI_IMAGE_MODELS | GOOGLE_IMAGE_MODELS


class CreateImageParams(BaseModel):
    prompt: str = Field(description="Text prompt to generate an image from.")
    model: str = Field(
        description=(
            "Image model slug. Allowed: gpt-image-1.5, gemini-3.1-flash-image-preview."
        )
    )
    aspect_ratio: AspectRatio = Field(
        default="square",
        description="Aspect ratio choice: square|landscape|portrait.",
    )
    guidance_attachments: list[str] = Field(
        default=[],
        description=(
            "Optional list of MessageAttachment UUIDs to use as visual reference when generating the image. "
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


def _pick_openai_size_str(aspect_ratio: AspectRatio) -> str:
    w, h = {
        "square": (1024, 1024),
        "landscape": (1536, 1024),
        "portrait": (1024, 1536),
    }[aspect_ratio]
    return f"{w}x{h}"


def _guess_filename(prompt: str, content_type: str | None) -> str:
    base = slugify((prompt or "").strip()[:80] or "image")
    ext = None
    if content_type:
        ext = mimetypes.guess_extension(content_type.split(";")[0].strip())
    if not ext:
        ext = ".png"
    return f"{base}-{uuid.uuid4().hex[:8]}{ext}"


def _generate_image_google(
    *,
    prompt: str,
    model: str,
    guidance_attachments: list,  # list of MessageAttachment instances
) -> tuple[bytes, str]:
    """Call Google Gemini image generation. Returns (raw_bytes, content_type)."""
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ValueError("google-genai is not installed. Run: uv add google-genai")

    api_key = os.environ.get("GOOGLE_CLOUD_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_CLOUD_API_KEY env var is not set")

    client = genai.Client(api_key=api_key)

    parts = []
    for att in guidance_attachments:
        try:
            with open(att.file.path, "rb") as f:
                image_bytes = f.read()
            parts.append(genai_types.Part.from_bytes(data=image_bytes, mime_type=att.content_type or "image/png"))
        except Exception:
            logger.warning("Could not read guidance attachment %s, skipping", att.id)

    parts.append(genai_types.Part.from_text(text=prompt))

    contents = [genai_types.Content(role="user", parts=parts)]
    config = genai_types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        max_output_tokens=8192,
        response_modalities=["TEXT", "IMAGE"],
        safety_settings=[
            genai_types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="OFF"),
            genai_types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="OFF"),
            genai_types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="OFF"),
            genai_types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="OFF"),
        ],
    )

    raw = None
    content_type = "image/png"
    for chunk in client.models.generate_content_stream(model=model, contents=contents, config=config):
        if not chunk.candidates:
            continue
        for part in chunk.candidates[0].content.parts:
            if part.inline_data and part.inline_data.data:
                data = part.inline_data.data
                if isinstance(data, str):
                    data = base64.b64decode(data)
                raw = data
                content_type = part.inline_data.mime_type or "image/png"
                break
        if raw is not None:
            break

    if not raw:
        raise ValueError("Google Gemini returned no image data")

    return raw, content_type


def _create_image_impl(
    *,
    prompt: str,
    model: str,
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

    # ---- Validate model allowlist ----
    model = (model or "").strip()
    if model not in ALL_IMAGE_MODELS:
        allowed = sorted(list(ALL_IMAGE_MODELS))
        raise ValueError(f"Unsupported image model '{model}'. Allowed: {', '.join(allowed)}")

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    # ---- Load conversation + resolve user ----
    try:
        conversation = Conversation.objects.select_related("organization", "chat_widget").get(
            id=conversation_id
        )
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = None

    # ---- Feature gating ----
    # Embeddable widget: allowed tools are already limited by ChatWidget.capabilities
    # (see ChatWidgetAgentTaskView). Visitors are not Django users, so org feature flags
    # for image-tools would wrongly block the model even when the widget enables create_image.
    if not conversation.chat_widget_id:
        enabled, _reason = FeatureFlagService.is_feature_enabled(
            "image-tools",
            organization=getattr(conversation, "organization", None),
            user=user,
        )
        if not enabled:
            raise ValueError("The 'image-tools' feature is not enabled.")

    # ---- Generate image bytes ----
    is_google = model in GOOGLE_IMAGE_MODELS
    size_used = _pick_openai_size_str(aspect_ratio)

    if is_google:
        # Load guidance attachment objects
        att_objects = []
        for att_id in guidance_attachments or []:
            try:
                att_objects.append(MessageAttachment.objects.get(id=att_id, kind="file"))
            except MessageAttachment.DoesNotExist:
                logger.warning("Guidance attachment %s not found, skipping", att_id)
        try:
            raw, content_type = _generate_image_google(
                prompt=prompt,
                model=model,
                guidance_attachments=att_objects,
            )
        except Exception as e:
            logger.exception("Failed to generate image via Google")
            raise ValueError(f"Failed to generate image: {str(e)}")
        source_image_url = f"google://{model}"
    else:
        content_type = "image/png"
        try:
            client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
            # Load guidance attachment objects for edit path
            att_objects = []
            for att_id in guidance_attachments or []:
                try:
                    att_objects.append(MessageAttachment.objects.get(id=att_id, kind="file"))
                except MessageAttachment.DoesNotExist:
                    logger.warning("Guidance attachment %s not found, skipping", att_id)

            if att_objects:
                # Use images.edit() when reference images are provided
                image_files = [open(att.file.path, "rb") for att in att_objects]
                try:
                    resp = client.images.edit(
                        model=model,
                        image=image_files,
                        prompt=prompt,
                        size=size_used,
                        quality="medium",
                    )
                finally:
                    for f in image_files:
                        f.close()
            else:
                resp = client.images.generate(
                    model=model,
                    prompt=prompt,
                    size=size_used,
                    quality="medium",
                )
            b64 = resp.data[0].b64_json
            if not b64:
                raise ValueError("OpenAI returned empty image data")
            raw = base64.b64decode(b64)
        except Exception as e:
            logger.exception("Failed to generate image via OpenAI")
            raise ValueError(f"Failed to generate image: {str(e)}")
        source_image_url = f"openai://{model}"

    # ---- Resolve agent (optional) ----
    agent_obj = None
    if agent_slug:
        try:
            from api.ai_layers.models import Agent

            agent_obj = Agent.objects.get(slug=agent_slug)
        except Exception:
            agent_obj = None

    filename = _guess_filename(prompt, content_type)
    file_obj = ContentFile(raw, name=filename)

    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent_obj,
        kind="file",
        file=file_obj,
        content_type=content_type,
        metadata={
            "prompt": prompt,
            "model": model,
            "aspect_ratio": aspect_ratio,
            "size": size_used,
            "source_image_url": source_image_url,
        },
    )

    # Bill image generation
    if user_id is not None:
        from api.consumption.tasks import async_register_image_generation
        organization_id = getattr(conversation.organization, "id", None)
        async_register_image_generation.delay(user_id, model, organization_id)

    # Display URL: either absolute (API_BASE_URL) or relative (/media/...)
    api_base = getattr(settings, "API_BASE_URL", None) or ""
    file_url = attachment.file.url if attachment.file else ""
    display_url = (
        f"{api_base.rstrip('/')}{file_url}" if api_base and file_url and not file_url.startswith("http") else file_url
    )

    name = slugify(prompt[:100]) or "image"
    return CreateImageResult(
        attachment_id=str(attachment.id),
        name=name,
        content=display_url,
        model=model,
        aspect_ratio=aspect_ratio,
        source_image_url=source_image_url,
    )


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
        model: str,
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
            "Allowed models: gpt-image-1.5, gemini-3.1-flash-image-preview. "
            "guidance_attachments is an optional list of MessageAttachment UUIDs to use as visual reference "
            "(only supported for Google models). "
            "Returns an attachment_id and a display URL (content) that will appear in the chat."
        ),
        "parameters": CreateImageParams,
        "function": create_image,
    }

