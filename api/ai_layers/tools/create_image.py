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

# For now we only allow the most capable OpenAI image model.
OPENAI_IMAGE_MODELS: set[str] = {"gpt-image-1.5"}


class CreateImageParams(BaseModel):
    prompt: str = Field(description="Text prompt to generate an image from.")
    model: str = Field(
        description=(
            "Image model slug. Allowed: gpt-image-1.5."
        )
    )
    aspect_ratio: AspectRatio = Field(
        default="square",
        description="Aspect ratio choice: square|landscape|portrait.",
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


def _create_image_impl(
    *,
    prompt: str,
    model: str,
    aspect_ratio: AspectRatio,
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
    if model not in OPENAI_IMAGE_MODELS:
        allowed = sorted(list(OPENAI_IMAGE_MODELS))
        raise ValueError(f"Unsupported image model '{model}'. Allowed: {', '.join(allowed)}")

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    # ---- Load conversation + resolve user ----
    try:
        conversation = Conversation.objects.select_related("organization").get(id=conversation_id)
    except Conversation.DoesNotExist:
        raise ValueError("Conversation not found")

    user = None
    if user_id is not None:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            user = None

    # ---- Feature gating (must match existing image generation endpoint) ----
    enabled, _reason = FeatureFlagService.is_feature_enabled(
        "image-tools",
        organization=getattr(conversation, "organization", None),
        user=user,
    )
    if not enabled:
        raise ValueError("The 'image-tools' feature is not enabled.")

    # ---- Generate image bytes (OpenAI returns base64) ----
    size_used = _pick_openai_size_str(aspect_ratio)
    content_type = "image/png"
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
        # Default output_format is png; we persist as a file attachment.
        resp = client.images.generate(
            model=model,
            prompt=prompt,
            size=size_used,
        )
        b64 = resp.data[0].b64_json
        if not b64:
            raise ValueError("OpenAI returned empty image data")
        raw = base64.b64decode(b64)
    except Exception as e:
        logger.exception("Failed to generate image via OpenAI")
        raise ValueError(f"Failed to generate image: {str(e)}")

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
            "source_image_url": f"openai://{model}",
        },
    )

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
        source_image_url=f"openai://{model}",
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("create_image requires conversation_id in tool context")

    def create_image(prompt: str, model: str, aspect_ratio: AspectRatio = "square") -> CreateImageResult:
        return _create_image_impl(
            prompt=prompt,
            model=model,
            aspect_ratio=aspect_ratio,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "create_image",
        "description": (
            "Generate an image from a text prompt and store it as a conversation attachment. "
            "Use this ONLY when the user asks to generate an image. "
            "Model must be: gpt-image-1.5. "
            "Returns an attachment_id and a display URL (content) that will appear in the chat."
        ),
        "parameters": CreateImageParams,
        "function": create_image,
    }

