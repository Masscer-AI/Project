from __future__ import annotations

import base64
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
OMNI_MODEL = "gemini-omni-1.1-flash-preview"
VIDEO_MODELS = {VEO_MODEL, OMNI_MODEL}
GOOGLE_CLOUD_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "masscer-492023")
GOOGLE_CLOUD_LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
OMNI_LOCATION = "global"
OMNI_RESOLUTION = "720p"
OMNI_TIMEOUT_SECONDS = 360
OMNI_DEFAULT_DURATION_SECONDS = 8
OMNI_MIN_DURATION_SECONDS = 3
OMNI_MAX_DURATION_SECONDS = 10
VEO_DURATION_SECONDS = 8.0

VideoAspectRatio = Literal["landscape", "portrait"]

_ASPECT_RATIO_TO_API = {
    "landscape": "16:9",
    "portrait": "9:16",
}

def _setup_google_credentials() -> str | None:
    credentials_json = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip().strip("'\"")
    if not credentials_json:
        return None

    if os.path.isfile(credentials_json):
        os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_json
        return credentials_json

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

def _cleanup_google_credentials(tmp_creds_path: str | None) -> None:
    if tmp_creds_path and tmp_creds_path.startswith(tempfile.gettempdir()):
        try:
            os.unlink(tmp_creds_path)
        except Exception:
            pass

def _guess_video_filename(prompt: str) -> str:
    base = slugify((prompt or "").strip()[:80] or "video")
    return f"{base}-{uuid.uuid4().hex[:8]}.mp4"

def _resolve_video_model(model: str | None) -> str:
    cleaned = (model or "").strip()
    if not cleaned:
        return VEO_MODEL
    if cleaned not in VIDEO_MODELS:
        raise ValueError(
            f"Unsupported video model '{cleaned}'. "
            f"Use {VEO_MODEL} or {OMNI_MODEL}."
        )
    return cleaned

def _omni_duration_seconds(duration_seconds: int | None) -> int:
    if duration_seconds is None:
        return OMNI_DEFAULT_DURATION_SECONDS
    if duration_seconds < OMNI_MIN_DURATION_SECONDS or duration_seconds > OMNI_MAX_DURATION_SECONDS:
        raise ValueError(
            f"Omni video duration must be between {OMNI_MIN_DURATION_SECONDS} "
            f"and {OMNI_MAX_DURATION_SECONDS} seconds."
        )
    return duration_seconds

def _load_image_attachment(attachment_id: str):
    from api.messaging.models import MessageAttachment

    try:
        image_att = MessageAttachment.objects.get(id=attachment_id.strip(), kind="file")
    except MessageAttachment.DoesNotExist:
        raise ValueError(f"Image attachment '{attachment_id}' not found.")
    if not image_att.file:
        raise ValueError("Image attachment has no file.")
    if not (image_att.content_type or "").startswith("image/"):
        raise ValueError("Attachment is not an image.")
    with open(image_att.file.path, "rb") as f:
        return f.read(), image_att.content_type or "image/png"

def _image_block(image_bytes: bytes, mime_type: str) -> dict:
    return {
        "type": "image",
        "data": base64.b64encode(image_bytes).decode("ascii"),
        "mime_type": mime_type or "image/png",
    }

def _video_block(video_bytes: bytes, mime_type: str) -> dict:
    return {
        "type": "video",
        "data": base64.b64encode(video_bytes).decode("ascii"),
        "mime_type": mime_type or "video/mp4",
    }

def _decode_media_data(raw) -> bytes | None:
    if isinstance(raw, str):
        return base64.b64decode(raw)
    if isinstance(raw, (bytes, bytearray)):
        return bytes(raw)
    return None

def _video_bytes_from_interaction(interaction) -> tuple[bytes, str]:
    candidates = []
    output_video = getattr(interaction, "output_video", None)
    if output_video is not None:
        candidates.append(output_video)
    for step in getattr(interaction, "steps", None) or []:
        if getattr(step, "type", None) != "model_output":
            continue
        for item in getattr(step, "content", None) or []:
            if getattr(item, "type", None) == "video":
                candidates.append(item)
    for item in candidates:
        raw = _decode_media_data(getattr(item, "data", None))
        if raw:
            return raw, str(getattr(interaction, "id", "") or "")
    status = getattr(interaction, "status", None)
    raise ValueError(f"Omni did not return a video (status={status}).")

def _omni_interaction(**kwargs):
    from google import genai

    client = genai.Client(
        vertexai=True,
        project=GOOGLE_CLOUD_PROJECT,
        location=OMNI_LOCATION,
    )
    return client.interactions.create(**kwargs)

def _generate_video_omni(
    *,
    prompt: str,
    aspect_ratio: VideoAspectRatio,
    duration_seconds: int,
    task: str,
    images: list[tuple[bytes, str]] | None = None,
    video_bytes: bytes | None = None,
    video_mime_type: str | None = None,
    previous_interaction_id: str | None = None,
) -> tuple[bytes, float, str]:
    inputs: list[dict] = []
    for image_bytes, mime_type in images or []:
        inputs.append(_image_block(image_bytes, mime_type))
    if video_bytes is not None and not previous_interaction_id:
        inputs.append(_video_block(video_bytes, video_mime_type or "video/mp4"))
    inputs.append({"type": "text", "text": prompt})

    response_format = {
        "type": "video",
        "resolution": OMNI_RESOLUTION,
        "duration": f"{duration_seconds}s",
        "delivery": "inline",
    }
    if task != "extend":
        response_format["aspect_ratio"] = _ASPECT_RATIO_TO_API[aspect_ratio]
    create_kwargs = {
        "model": OMNI_MODEL,
        "input": inputs,
        "response_format": response_format,
        "generation_config": {"video_config": {"task": task}},
        "store": True,
        "background": False,
        "timeout": OMNI_TIMEOUT_SECONDS,
    }
    if previous_interaction_id:
        create_kwargs["previous_interaction_id"] = previous_interaction_id

    interaction = _omni_interaction(**create_kwargs)
    raw, interaction_id = _video_bytes_from_interaction(interaction)
    return raw, float(duration_seconds), interaction_id

def _generate_video_veo(
    *,
    prompt: str,
    image_bytes: bytes | None,
    image_mime_type: str | None,
    aspect_ratio: VideoAspectRatio,
) -> tuple[bytes, float]:
    try:
        from google import genai
        from google.genai import types as genai_types
    except ImportError:
        raise ValueError("google-genai is not installed. Run: uv add google-genai")

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
        aspect_ratio=_ASPECT_RATIO_TO_API[aspect_ratio],
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

    veo_result = operation.result
    rai_count = getattr(veo_result, "rai_media_filtered_count", None)
    rai_reasons = getattr(veo_result, "rai_media_filtered_reasons", None) or []
    logger.info(
        "Veo response: generated_videos=%s, rai_media_filtered_count=%s, rai_reasons=%s",
        len(veo_result.generated_videos) if veo_result.generated_videos else 0,
        rai_count,
        rai_reasons,
    )

    generated_videos = veo_result.generated_videos or []

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

    return raw, VEO_DURATION_SECONDS

def _require_video_tools(conversation, user):
    from api.ai_layers.tools.embedded_channels import (
        conversation_uses_capability_gated_media_tools,
    )
    from api.authenticate.services import FeatureFlagService

    if conversation_uses_capability_gated_media_tools(conversation):
        return
    enabled, _reason = FeatureFlagService.is_feature_enabled(
        "video-tools",
        organization=getattr(conversation, "organization", None),
        user=user,
    )
    if not enabled:
        raise ValueError("The 'video-tools' feature is not enabled.")

def _load_video_context(conversation_id: str, user_id: int | None):
    from django.contrib.auth.models import User

    from api.messaging.models import Conversation

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

    _require_video_tools(conversation, user)
    return conversation, user

def _load_agent(agent_slug: str | None):
    if not agent_slug:
        return None
    try:
        from api.ai_layers.models import Agent

        return Agent.objects.get(slug=agent_slug)
    except Exception:
        return None

def _display_url(attachment) -> str:
    from django.conf import settings

    api_base = getattr(settings, "API_BASE_URL", None) or ""
    file_url = attachment.file.url if attachment.file else ""
    if api_base and file_url and not file_url.startswith("http"):
        return f"{api_base.rstrip('/')}{file_url}"
    return file_url

def _persist_generated_video(
    *,
    conversation,
    user,
    agent_slug: str | None,
    prompt: str,
    raw: bytes,
    model: str,
    aspect_ratio: VideoAspectRatio,
    duration_seconds: float,
    source_image_id: str | None,
    reference_attachment_ids: list[str],
    omni_interaction_id: str | None,
    source_video_attachment_id: str | None,
    user_id: int | None,
):
    from api.messaging.models import MessageAttachment

    filename = _guess_video_filename(prompt)
    metadata = {
        "prompt": prompt,
        "model": model,
        "aspect_ratio": aspect_ratio,
        "source_image_attachment_id": source_image_id,
        "duration_seconds": duration_seconds,
        "source_video_url": f"google://{model}",
    }
    if reference_attachment_ids:
        metadata["reference_attachment_ids"] = reference_attachment_ids
    if omni_interaction_id:
        metadata["omni_interaction_id"] = omni_interaction_id
    if source_video_attachment_id:
        metadata["source_video_attachment_id"] = source_video_attachment_id

    attachment = MessageAttachment.objects.create(
        conversation=conversation,
        user=user,
        agent=_load_agent(agent_slug),
        kind="file",
        file=ContentFile(raw, name=filename),
        content_type="video/mp4",
        metadata=metadata,
    )

    if user_id is not None:
        try:
            from api.consumption.tasks import async_register_video_generation

            organization_id = getattr(conversation.organization, "id", None)
            async_register_video_generation.delay(
                user_id, model, duration_seconds, organization_id
            )
        except Exception:
            logger.warning("Failed to queue video billing task", exc_info=True)

    return attachment

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
        description="landscape (16:9) or portrait (9:16). Square is not supported.",
    )
    model: str = Field(
        default="",
        description=(
            "Optional model slug. Leave empty for Google Veo 3.1 "
            f"({VEO_MODEL}). Pass {OMNI_MODEL} for Gemini Omni, "
            "which also accepts reference images and a duration from 3 to 10 seconds."
        ),
    )
    duration_seconds: int | None = Field(
        default=None,
        description=(
            "Gemini Omni only. Length in seconds, from 3 to 10. Defaults to 8. Ignored for Veo."
        ),
    )
    reference_attachment_ids: list[str] = Field(
        default_factory=list,
        description=(
            "Gemini Omni only. Extra image MessageAttachment UUIDs used as visual references."
        ),
    )

class GenerateVideoResult(BaseModel):
    attachment_id: str = Field(description="UUID of the created video MessageAttachment.")
    name: str = Field(description="Short slugified name for display.")
    content: str = Field(description="Display URL for the generated video.")
    model: str = Field(description="Model used for generation.")
    aspect_ratio: VideoAspectRatio = Field(description="Aspect ratio requested (16:9 or 9:16).")
    duration_seconds: float = Field(description="Duration of the generated video in seconds.")

def _generate_video_impl(
    *,
    prompt: str,
    image_attachment_id: str,
    aspect_ratio: VideoAspectRatio,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
    model: str | None = None,
    duration_seconds: int | None = None,
    reference_attachment_ids: list[str] | None = None,
) -> GenerateVideoResult:
    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    resolved_model = _resolve_video_model(model)
    reference_ids = [item.strip() for item in (reference_attachment_ids or []) if item and item.strip()]
    if reference_ids and resolved_model != OMNI_MODEL:
        raise ValueError(
            f"Reference images require model {OMNI_MODEL}. "
            "Pass that model, or omit reference_attachment_ids to use Veo."
        )

    omni_duration = None
    if resolved_model == OMNI_MODEL:
        omni_duration = _omni_duration_seconds(duration_seconds)

    conversation, user = _load_video_context(conversation_id, user_id)

    image_bytes = None
    image_mime_type = None
    source_image_id = None
    images: list[tuple[bytes, str]] = []

    if image_attachment_id and image_attachment_id.strip():
        image_bytes, image_mime_type = _load_image_attachment(image_attachment_id)
        source_image_id = image_attachment_id.strip()
        images.append((image_bytes, image_mime_type))

    for ref_id in reference_ids:
        if ref_id == source_image_id:
            continue
        images.append(_load_image_attachment(ref_id))

    tmp_creds_path = _setup_google_credentials()
    omni_interaction_id = None
    try:
        if resolved_model == OMNI_MODEL:
            if reference_ids:
                task = "reference_to_video"
            elif images:
                task = "image_to_video"
            else:
                task = "text_to_video"
            raw, billed_duration, omni_interaction_id = _generate_video_omni(
                prompt=prompt,
                aspect_ratio=aspect_ratio,
                duration_seconds=omni_duration,
                task=task,
                images=images,
            )
        else:
            raw, billed_duration = _generate_video_veo(
                prompt=prompt,
                image_bytes=image_bytes,
                image_mime_type=image_mime_type,
                aspect_ratio=aspect_ratio,
            )
    except Exception as e:
        logger.exception("Failed to generate video via %s", resolved_model)
        raise ValueError(f"Failed to generate video: {str(e)}")
    finally:
        _cleanup_google_credentials(tmp_creds_path)

    attachment = _persist_generated_video(
        conversation=conversation,
        user=user,
        agent_slug=agent_slug,
        prompt=prompt,
        raw=raw,
        model=resolved_model,
        aspect_ratio=aspect_ratio,
        duration_seconds=billed_duration,
        source_image_id=source_image_id,
        reference_attachment_ids=reference_ids,
        omni_interaction_id=omni_interaction_id,
        source_video_attachment_id=None,
        user_id=user_id,
    )
    name = slugify(prompt[:100]) or "video"
    return GenerateVideoResult(
        attachment_id=str(attachment.id),
        name=name,
        content=_display_url(attachment),
        model=resolved_model,
        aspect_ratio=aspect_ratio,
        duration_seconds=billed_duration,
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
        model: str = "",
        duration_seconds: int | None = None,
        reference_attachment_ids: list[str] | None = None,
    ) -> GenerateVideoResult:
        return _generate_video_impl(
            prompt=prompt,
            image_attachment_id=image_attachment_id,
            aspect_ratio=aspect_ratio,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
            model=model,
            duration_seconds=duration_seconds,
            reference_attachment_ids=reference_attachment_ids,
        )

    return {
        "name": "generate_video",
        "description": (
            "Generate a short video. "
            f"Default model is Google Veo 3.1 ({VEO_MODEL}). "
            f"Pass model {OMNI_MODEL} for Gemini Omni when the user asks for Omni "
            "or supplies reference images. "
            "prompt describes the motion and scene. "
            "aspect_ratio is landscape (16:9) or portrait (9:16). "
            "image_attachment_id is an optional image MessageAttachment UUID used as the first frame. "
            "duration_seconds is Omni only, from 3 to 10, default 8. "
            "reference_attachment_ids is Omni only. "
            "Video generation takes up to 6 minutes — inform the user it may take a moment. "
            "Returns an attachment_id and a display URL for the generated video."
        ),
        "parameters": GenerateVideoParams,
        "function": generate_video,
    }
