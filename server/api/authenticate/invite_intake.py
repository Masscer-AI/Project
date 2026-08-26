"""Structured optional fields captured when inviting a client/supplier."""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

RFC_PATTERN = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")


class InviteIntake(BaseModel):
    model_config = ConfigDict(extra="forbid")

    person_type: Optional[Literal["persona_fisica", "persona_moral"]] = None
    counterparty_role: Optional[Literal["cliente", "proveedor", "ambos"]] = None
    relationship_status: Optional[Literal["nuevo", "existente"]] = None
    rfc: Optional[str] = None

    @field_validator("rfc", mode="before")
    @classmethod
    def normalize_rfc(cls, value):
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("rfc must be a string")
        cleaned = value.strip().upper().replace(" ", "")
        if not RFC_PATTERN.fullmatch(cleaned):
            raise ValueError("Invalid RFC")
        return cleaned


def normalize_invite_intake(raw) -> dict:
    if raw is None or raw == "":
        return {}
    if not isinstance(raw, dict):
        raise ValueError("intake must be a JSON object")
    cleaned = {
        key: value
        for key, value in raw.items()
        if value not in (None, "")
    }
    try:
        return InviteIntake.model_validate(cleaned).model_dump(
            mode="json", exclude_none=True
        )
    except ValidationError as exc:
        raise ValueError("Invalid intake") from exc
