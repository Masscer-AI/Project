"""Notification sound preferences (validated JSON on UserPreferences)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

# Built-in tone identifiers — add new refs here as more tones ship.
NotificationToneRef = Literal[
    "chime_success_ascending",
    "chime_error_descending",
]

NOTIFICATION_TONE_REFS: tuple[str, ...] = (
    "chime_success_ascending",
    "chime_error_descending",
)

# Catalog for future tone-picker UIs / public API.
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
