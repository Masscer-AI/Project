"""Notification sound preferences (validated JSON on UserPreferences)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

NotificationToneRef = Literal[
    "chime_success_ascending",
    "chime_error_descending",
    "magic_notification_riser",
    "magic_ascending_three_1",
    "magic_ascending_three_2",
    "magic_ascending_three_3",
    "magic_ascending_three_4",
    "magic_descending_two",
    "error_beep_short",
    "error_sharp_high",
    "error_descending_two_a",
    "error_descending_two_b",
]

NOTIFICATION_TONE_REFS: tuple[str, ...] = (
    "chime_success_ascending",
    "chime_error_descending",
    "magic_notification_riser",
    "magic_ascending_three_1",
    "magic_ascending_three_2",
    "magic_ascending_three_3",
    "magic_ascending_three_4",
    "magic_descending_two",
    "error_beep_short",
    "error_sharp_high",
    "error_descending_two_a",
    "error_descending_two_b",
)

NOTIFICATION_TONE_CATALOG: list[dict[str, str]] = [
    {
        "ref": "chime_success_ascending",
        "label_key": "notification-tone-chime-success-ascending",
        "kind": "success",
    },
    {
        "ref": "chime_error_descending",
        "label_key": "notification-tone-chime-error-descending",
        "kind": "error",
    },
    {
        "ref": "magic_notification_riser",
        "label_key": "notification-tone-magic-notification-riser",
        "kind": "success",
    },
    {
        "ref": "magic_ascending_three_1",
        "label_key": "notification-tone-magic-ascending-three-1",
        "kind": "success",
    },
    {
        "ref": "magic_ascending_three_2",
        "label_key": "notification-tone-magic-ascending-three-2",
        "kind": "success",
    },
    {
        "ref": "magic_ascending_three_3",
        "label_key": "notification-tone-magic-ascending-three-3",
        "kind": "success",
    },
    {
        "ref": "magic_ascending_three_4",
        "label_key": "notification-tone-magic-ascending-three-4",
        "kind": "success",
    },
    {
        "ref": "magic_descending_two",
        "label_key": "notification-tone-magic-descending-two",
        "kind": "success",
    },
    {
        "ref": "error_beep_short",
        "label_key": "notification-tone-error-beep-short",
        "kind": "error",
    },
    {
        "ref": "error_sharp_high",
        "label_key": "notification-tone-error-sharp-high",
        "kind": "error",
    },
    {
        "ref": "error_descending_two_a",
        "label_key": "notification-tone-error-descending-two-a",
        "kind": "error",
    },
    {
        "ref": "error_descending_two_b",
        "label_key": "notification-tone-error-descending-two-b",
        "kind": "error",
    },
]

class NotificationSettings(BaseModel):
    """User notification sound preferences."""

    model_config = ConfigDict(extra="forbid")

    activated: bool = Field(
        default=True,
        description="Master switch; when false, no notification sounds play.",
    )
    volume: float = Field(
        default=0.12,
        ge=0.0,
        le=1.0,
        description="Linear gain 0 (mute) to 1 (full).",
    )
    success_tone_ref: NotificationToneRef = Field(
        default="chime_success_ascending",
        description="Tone played on successful async events (e.g. assistant reply ready).",
    )
    failure_tone_ref: NotificationToneRef = Field(
        default="chime_error_descending",
        description="Tone played on error events.",
    )

def default_notification_settings_dict() -> dict[str, Any]:
    return NotificationSettings().model_dump()

def normalize_notification_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Merge stored JSON with defaults and validate."""
    base = default_notification_settings_dict()
    if not raw:
        return base
    if not isinstance(raw, dict):
        raise ValidationError.from_exception_data(
            "notification_settings",
            [{"type": "dict_type", "loc": (), "input": raw, "msg": "Expected object"}],
        )
    return NotificationSettings.model_validate({**base, **raw}).model_dump()
