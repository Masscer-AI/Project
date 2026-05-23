"""
Tool: generate_video

Generates a video using Google Veo 3.1 (Vertex AI).
Supports text-to-video and image-to-video (when an image attachment is provided).

Authentication uses a service account JSON stored in the GOOGLE_APPLICATION_CREDENTIALS_JSON
environment variable (minified single-line JSON). The tool writes it to a temp file and sets
GOOGLE_APPLICATION_CREDENTIALS before calling the Vertex AI client.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
import uuid
from typing import Literal

from django.core.files.base import ContentFile
from django.utils.text import slugify
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

VEO_MODEL = "veo-3.1-generate-001"
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "masscer-492023")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")

# $0.40 per second of generated video
VEO_PRICE_PER_SECOND_USD = 0.40

# Veo on Vertex AI only supports 16:9 and 9:16 (see GenerateVideosConfig.aspect_ratio).
VideoAspectRatio = Literal["landscape", "portrait"]

_ASPECT_RATIO_TO_VEO = {
    "landscape": "16:9",
    "portrait": "9:16",
}


class GenerateVideoParams(BaseModel):
    prompt: str = Field(
        description="Text prompt describing the motion and scene for the video."
    )
    image_attachment_id: str = Field(
        default="",
        description=(
            "Optional UUID of an existing image MessageAttachment to use as the first frame. "
            "Leave empty for text-to-video generation."
        ),
    )
    aspect_ratio: VideoAspectRatio = Field(
        default="landscape",
        description="Veo supports only landscape (16:9) or portrait (9:16), not square.",
    )


class GenerateVideoResult(BaseModel):
    attachment_id: str = Field(description="UUID of the created video MessageAttachment.")
    name: str = Field(description="Short slugified name for display.")
    content: str = Field(description="Display URL for the generated video.")
    model: str = Field(description="Model used for generation.")
    aspect_ratio: VideoAspectRatio = Field(description="Aspect ratio requested (16:9 or 9:16).")
    duration_seconds: float = Field(description="Duration of the generated video in seconds.")


def _setup_google_credentials() -> str | None:
    """
    Write GOOGLE_APPLICATION_CREDENTIALS_JSON to a temp file and set
    GOOGLE_APPLICATION_CREDENTIALS to its path. Returns the temp file path
    (caller is responsible for cleanup), or None if the env var is not set.
    """
    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip().strip("'\"")
    if not credentials_json:
        return None

    # Already a file path — nothing to do
    if os.path.isfile(credentials_json):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_json
        return credentials_json

    # Validate JSON
    try:
        json.loads(credentials_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON: {e}")

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, prefix="gcp_creds_"
    )
    tmp.write(credentials_json)
    tmp.close()
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = tmp.name
    return tmp.name


def _guess_video_filename(prompt: str) -> str:
    base = slugify((prompt or "").strip()[:80] or "video")
    return f"{base}-{uuid.uuid4().hex[:8]}.mp4"


def _generate_video_veo(
    *,
    prompt: str,
    image_bytes: bytes | None,
    image_mime_type: str | None,
    aspect_ratio: VideoAspectRatio,
) -> tuple[bytes, float]:
    """
    Call Veo 3.1 via the google-genai SDK.
    Supports text-to-video (image_bytes=None) and image-to-video.
    Returns (video_bytes, duration_seconds).
    """
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ValueError("google-genai is not installed. Run: uv add google-genai")

    import base64

    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location=GOOGLE_CLOUD_LOCATION,
    )

    if image_bytes is not None:
        source = genai_types.GenerateVideosSource(
            prompt=prompt,
            image=genai_types.Image(
                image_bytes=image_bytes,
                mime_type=image_mime_type or "image/png",
            ),
        )
    else:
        source = genai_types.GenerateVideosSource(prompt=prompt)

    config = genai_types.GenerateVideosConfig(
        aspect_ratio=_ASPECT_RATIO_TO_VEO[aspect_ratio],
        number_of_videos=1,
        duration_seconds=8,
        generate_audio=True,
        resolution="720p",
    )

    operation = client.models.generate_videos(
        model=VEO_MODEL,
        source=source,
        config=config,
    )

    # Poll until done
    max_wait_seconds = 360
    poll_interval = 15
    elapsed = 0
    while not operation.done:
        if elapsed >= max_wait_seconds:
            raise ValueError("Video generation timed out after 6 minutes.")
        logger.info("Veo operation in progress... (%ds elapsed)", elapsed)
        time.sleep(poll_interval)
        elapsed += poll_interval
        operation = client.operations.get(operation)

    if getattr(operation, "error", None):
        logger.error("Veo operation error: %s", operation.error)
        raise ValueError(f"Veo generation failed: {operation.error}")

    if not operation.result:
        logger.error("Veo operation has no result. Full operation: %s", operation)
        raise ValueError("Veo generation failed — no result returned.")

    result = operation.result
    rai_count = getattr(result, "rai_media_filtered_count", None)
    rai_reasons = getattr(result, "rai_media_filtered_reasons", None) or []
    logger.info(
        "Veo response: generated_videos=%s, rai_media_filtered_count=%s, rai_reasons=%s",
        len(result.generated_videos) if result.generated_videos else 0,
        rai_count,
        rai_reasons,
    )

    generated_videos = result.generated_videos or []

    if not generated_videos or not generated_videos[0].video:
        if rai_count or rai_reasons:
            detail = "; ".join(rai_reasons) if rai_reasons else f"filtered_count={rai_count}"
            raise ValueError(
                "Veo did not return a video — Google's safety filters blocked this request "
                f"({detail}). This is not a billing quota issue; try a different prompt or image, or retry."
            )
        raise ValueError(
            "Veo returned no video data (empty generated_videos). "
            "If this persists, check Cloud project quotas and Vertex AI Veo availability for your region."
        )

    video = generated_videos[0].video
    logger.info("Veo video object: %s, video_bytes type=%s", video, type(video.video_bytes))
    raw = video.video_bytes
    if isinstance(raw, str):
        raw = base64.b64decode(raw)
    if not raw and getattr(video, "uri", None):
        logger.info("Veo returned video URI only; downloading via client.files.download")
        raw = client.files.download(file=video)

    if not raw:
        raise ValueError("Veo returned a video object with no bytes and no downloadable URI.")

    duration = 8.0  # Veo 3.1 default clip length
    return raw, duration


def _generate_video_impl(
    *,
    prompt: str,
    image_attachment_id: str,
    aspect_ratio: VideoAspectRatio,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> GenerateVideoResult:
    from django.conf import settings
    from django.contrib.auth.models import User

    from api.authenticate.services import FeatureFlagService
    from api.messaging.models import Conversation, MessageAttachment

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
    from api.ai_layers.tools.embedded_channels import (
        conversation_uses_capability_gated_media_tools,
    )

    if not conversation_uses_capability_gated_media_tools(conversation):
        enabled, _reason = FeatureFlagService.is_feature_enabled(
            "video-tools",
            organization=getattr(conversation, "organization", None),
            user=user,
        )
        if not enabled:
            raise ValueError("The 'video-tools' feature is not enabled.")

    # ---- Load source image attachment (optional) ----
    image_bytes = None
    image_mime_type = None
    source_image_id = None

    if image_attachment_id and image_attachment_id.strip():
        try:
            image_att = MessageAttachment.objects.get(id=image_attachment_id.strip(), kind="file")
            if not image_att.file:
                raise ValueError("Image attachment has no file.")
            if not (image_att.content_type or "").startswith("image/"):
                raise ValueError("Attachment is not an image.")
            with open(image_att.file.path, "rb") as f:
                image_bytes = f.read()
            image_mime_type = image_att.content_type
            source_image_id = image_attachment_id.strip()
        except MessageAttachment.DoesNotExist:
            raise ValueError(f"Image attachment '{image_attachment_id}' not found.")

    # ---- Set up Google credentials ----
    tmp_creds_path = _setup_google_credentials()

    # ---- Generate video ----
    try:
        raw, duration_seconds = _generate_video_veo(
            prompt=prompt,
            image_bytes=image_bytes,
            image_mime_type=image_mime_type,
            aspect_ratio=aspect_ratio,
        )
    except Exception as e:
        logger.exception("Failed to generate video via Veo")
        raise ValueError(f"Failed to generate video: {str(e)}")
    finally:
        if tmp_creds_path and tmp_creds_path.startswith(tempfile.gettempdir()):
            try:
                os.unlink(tmp_creds_path)
            except Exception:
                pass

    # ---- Resolve agent ----
    agent_obj = None
    if agent_slug:
        try:
            from api.ai_layers.models import Agent
            agent_obj = Agent.objects.get(slug=agent_slug)
        except Exception:
            agent_obj = None

    # ---- Save as MessageAttachment ----
    filename = _guess_video_filename(prompt)
    file_obj = ContentFile(raw, name=filename)

    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=agent_obj,
        kind="file",
        file=file_obj,
        content_type="video/mp4",
        metadata={
            "prompt": prompt,
            "model": VEO_MODEL,
            "aspect_ratio": aspect_ratio,
            "source_image_attachment_id": source_image_id,
            "duration_seconds": duration_seconds,
            "source_video_url": f"google://{VEO_MODEL}",
        },
    )

    # ---- Bill video generation ----
    if user_id is not None:
        try:
            from api.consumption.tasks import async_register_video_generation
            organization_id = getattr(conversation.organization, "id", None)
            async_register_video_generation.delay(user_id, VEO_MODEL, duration_seconds, organization_id)
        except Exception:
            logger.warning("Failed to queue video billing task", exc_info=True)

    # ---- Build display URL ----
    api_base = getattr(settings, "API_BASE_URL", None) or ""
    file_url = attachment.file.url if attachment.file else ""
    display_url = (
        f"{api_base.rstrip('/')}{file_url}"
        if api_base and file_url and not file_url.startswith("http")
        else file_url
    )

    name = slugify(prompt[:100]) or "video"
    return GenerateVideoResult(
        attachment_id=str(attachment.id),
        name=name,
        content=display_url,
        model=VEO_MODEL,
        aspect_ratio=aspect_ratio,
        duration_seconds=duration_seconds,
    )


def get_tool(
    conversation_id: str | None = None,
    user_id: int | None = None,
    agent_slug: str | None = None,
    **kwargs,
) -> dict:
    if not conversation_id:
        raise ValueError("generate_video requires conversation_id in tool context")

    def generate_video(
        prompt: str,
        image_attachment_id: str = "",
        aspect_ratio: VideoAspectRatio = "landscape",
    ) -> GenerateVideoResult:
        return _generate_video_impl(
            prompt=prompt,
            image_attachment_id=image_attachment_id,
            aspect_ratio=aspect_ratio,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "generate_video",
        "description": (
            "Generate a short video using Google Veo 3.1. "
            "Provide a prompt describing the motion and scene. "
            "aspect_ratio: landscape (16:9) or portrait (9:16) only — Veo does not support square; default landscape. "
            "Optionally provide image_attachment_id (UUID of an existing image MessageAttachment) "
            "to use it as the first frame — if omitted, generates from text only. "
            "Video generation takes up to 6 minutes — inform the user it may take a moment. "
            "Returns an attachment_id and a display URL for the generated video."
        ),
        "parameters": GenerateVideoParams,
        "function": generate_video,
    }
