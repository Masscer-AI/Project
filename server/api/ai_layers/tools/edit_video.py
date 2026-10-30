from __future__ import annotations

from typing import Literal

from django.utils.text import slugify
from pydantic import BaseModel, Field

from api.ai_layers.tools.generate_video import (
    OMNI_DEFAULT_DURATION_SECONDS,
    OMNI_MAX_DURATION_SECONDS,
    OMNI_MIN_DURATION_SECONDS,
    OMNI_MODEL,
    VideoAspectRatio,
    _cleanup_google_credentials,
    _display_url,
    _generate_video_omni,
    _load_image_attachment,
    _load_video_context,
    _omni_duration_seconds,
    _persist_generated_video,
    _setup_google_credentials,
)

VideoEditAction = Literal["edit", "extend"]

class EditVideoParams(BaseModel):
    prompt: str = Field(description="What to change, or how the video should continue.")
    video_attachment_id: str = Field(
        description="UUID of the existing video MessageAttachment to edit or extend."
    )
    action: VideoEditAction = Field(
        default="edit",
        description="edit changes the clip. extend continues it past the end.",
    )
    reference_attachment_ids: list[str] = Field(
        default_factory=list,
        description="Optional image MessageAttachment UUIDs to guide the edit or extension.",
    )
    duration_seconds: int | None = Field(
        default=None,
        description="Length in seconds, from 3 to 10. Defaults to the source clip, or 8.",
    )

class EditVideoResult(BaseModel):
    attachment_id: str = Field(description="UUID of the created video MessageAttachment.")
    name: str = Field(description="Short slugified name for display.")
    content: str = Field(description="Display URL for the edited video.")
    model: str = Field(description="Model used for the edit.")
    aspect_ratio: VideoAspectRatio = Field(description="Aspect ratio of the result.")
    duration_seconds: float = Field(description="Duration billed for the result, in seconds.")

def _source_aspect_ratio(metadata: dict) -> VideoAspectRatio:
    stored = metadata.get("aspect_ratio")
    if stored in ("landscape", "portrait"):
        return stored
    return "landscape"

def _source_duration(metadata: dict, requested: int | None) -> int:
    if requested is not None:
        return _omni_duration_seconds(requested)
    stored = metadata.get("duration_seconds")
    if isinstance(stored, (int, float)) and OMNI_MIN_DURATION_SECONDS <= stored <= OMNI_MAX_DURATION_SECONDS:
        return int(stored)
    return OMNI_DEFAULT_DURATION_SECONDS

def _edit_video_impl(
    *,
    prompt: str,
    video_attachment_id: str,
    action: VideoEditAction,
    reference_attachment_ids: list[str] | None,
    duration_seconds: int | None,
    conversation_id: str,
    user_id: int | None,
    agent_slug: str | None,
) -> EditVideoResult:
    from api.messaging.models import MessageAttachment

    prompt = (prompt or "").strip()
    if not prompt:
        raise ValueError("prompt is required")
    if action not in ("edit", "extend"):
        raise ValueError("action must be edit or extend.")
    attachment_id = (video_attachment_id or "").strip()
    if not attachment_id:
        raise ValueError("video_attachment_id is required")

    conversation, user = _load_video_context(conversation_id, user_id)

    try:
        video_att = MessageAttachment.objects.get(id=attachment_id, kind="file")
    except MessageAttachment.DoesNotExist:
        raise ValueError(f"Video attachment '{attachment_id}' not found.")
    if not video_att.file:
        raise ValueError("Video attachment has no file.")
    if not (video_att.content_type or "").startswith("video/"):
        raise ValueError("Attachment is not a video.")

    metadata = video_att.metadata or {}
    previous_interaction_id = (metadata.get("omni_interaction_id") or "").strip() or None
    stored_duration = metadata.get("duration_seconds")
    if (
        previous_interaction_id is None
        and isinstance(stored_duration, (int, float))
        and float(stored_duration) > OMNI_MAX_DURATION_SECONDS
    ):
        raise ValueError(
            "Omni can only edit or extend uploaded videos that are 10 seconds or shorter."
        )

    aspect_ratio = _source_aspect_ratio(metadata)
    omni_duration = _source_duration(metadata, duration_seconds)
    reference_ids = [item.strip() for item in (reference_attachment_ids or []) if item and item.strip()]
    images = [_load_image_attachment(ref_id) for ref_id in reference_ids]

    video_bytes = None
    video_mime = video_att.content_type
    if previous_interaction_id is None:
        with open(video_att.file.path, "rb") as f:
            video_bytes = f.read()

    tmp_creds_path = _setup_google_credentials()
    try:
        raw, billed_duration, omni_interaction_id = _generate_video_omni(
            prompt=prompt,
            aspect_ratio=aspect_ratio,
            duration_seconds=omni_duration,
            task=action,
            images=images,
            video_bytes=video_bytes,
            video_mime_type=video_mime,
            previous_interaction_id=previous_interaction_id,
        )
    except Exception as e:
        raise ValueError(f"Failed to edit video: {str(e)}")
    finally:
        _cleanup_google_credentials(tmp_creds_path)

    attachment = _persist_generated_video(
        conversation=conversation,
        user=user,
        agent_slug=agent_slug,
        prompt=prompt,
        raw=raw,
        model=OMNI_MODEL,
        aspect_ratio=aspect_ratio,
        duration_seconds=billed_duration,
        source_image_id=None,
        reference_attachment_ids=reference_ids,
        omni_interaction_id=omni_interaction_id,
        source_video_attachment_id=attachment_id,
        user_id=user_id,
    )
    name = slugify(prompt[:100]) or "video"
    return EditVideoResult(
        attachment_id=str(attachment.id),
        name=name,
        content=_display_url(attachment),
        model=OMNI_MODEL,
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
        raise ValueError("edit_video requires conversation_id in tool context")

    def edit_video(
        prompt: str,
        video_attachment_id: str,
        action: VideoEditAction = "edit",
        reference_attachment_ids: list[str] | None = None,
        duration_seconds: int | None = None,
    ) -> EditVideoResult:
        return _edit_video_impl(
            prompt=prompt,
            video_attachment_id=video_attachment_id,
            action=action,
            reference_attachment_ids=reference_attachment_ids,
            duration_seconds=duration_seconds,
            conversation_id=conversation_id,
            user_id=user_id,
            agent_slug=agent_slug,
        )

    return {
        "name": "edit_video",
        "description": (
            "Edit or extend an existing video with Gemini Omni. "
            "prompt describes the change or the continuation. "
            "video_attachment_id is the UUID of the video MessageAttachment. "
            "action is edit (change the clip) or extend (continue past the end). "
            "reference_attachment_ids are optional image UUIDs. "
            "Videos made by Gemini Omni are edited from their saved interaction. "
            "Other uploaded clips must be 10 seconds or shorter. "
            "Takes up to 6 minutes. Returns an attachment_id and a display URL."
        ),
        "parameters": EditVideoParams,
        "function": edit_video,
    }
