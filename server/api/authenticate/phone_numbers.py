"""Pydantic-validated phone numbers stored on UserProfile._phone_numbers."""

from __future__ import annotations

import re
from typing import Any

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    RootModel,
    field_validator,
    model_validator,
)

_DIGITS_RE = re.compile(r"[^\d]")


def _digits_only(value: str) -> str:
    return _DIGITS_RE.sub("", value or "")


class PhoneNumber(BaseModel):
    model_config = ConfigDict(extra="forbid")

    country_code: str = Field(
        description="Country calling code digits only (no +), e.g. '1' or '52'."
    )
    number: str = Field(
        description="National number digits only (no spaces/dashes)."
    )
    is_default: bool = False

    @field_validator("country_code", "number", mode="before")
    @classmethod
    def normalize_digits(cls, value: Any) -> str:
        if value is None:
            raise ValueError("must be a non-empty digit string")
        digits = _digits_only(str(value))
        if not digits:
            raise ValueError("must contain at least one digit")
        return digits

    @model_validator(mode="after")
    def validate_e164_length(self) -> PhoneNumber:
        # E.164 max is 15 digits including country code.
        total = len(self.country_code) + len(self.number)
        if total > 15:
            raise ValueError(
                f"phone number exceeds E.164 maximum of 15 digits (got {total})"
            )
        if len(self.country_code) > 3:
            raise ValueError("country_code must be at most 3 digits")
        if len(self.number) < 4:
            raise ValueError("number must contain at least 4 digits")
        return self

    def e164_digits(self) -> str:
        """Full international number digits (no +), for WhatsApp matching."""
        return f"{self.country_code}{self.number}"

    def to_json_dict(self) -> dict[str, Any]:
        return self.model_dump()


class PhoneNumbers(RootModel[list[PhoneNumber]]):
    root: list[PhoneNumber] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_list_invariants(self) -> PhoneNumbers:
        if len(self.root) > 10:
            raise ValueError("at most 10 phone numbers are allowed")

        seen: set[str] = set()
        default_count = 0
        for entry in self.root:
            key = entry.e164_digits()
            if key in seen:
                raise ValueError(f"duplicate phone number: {key}")
            seen.add(key)
            if entry.is_default:
                default_count += 1

        if default_count > 1:
            raise ValueError("at most one phone number may have is_default=True")

        # If none marked default and list non-empty, promote the first.
        if self.root and default_count == 0:
            self.root[0].is_default = True

        return self

    def to_json_list(self) -> list[dict[str, Any]]:
        return [entry.to_json_dict() for entry in self.root]

    def as_e164_set(self) -> set[str]:
        return {entry.e164_digits() for entry in self.root}

    def default_or_first(self) -> PhoneNumber | None:
        for entry in self.root:
            if entry.is_default:
                return entry
        return self.root[0] if self.root else None


def default_phone_numbers_list() -> list[dict[str, Any]]:
    return []


def parse_phone_numbers(raw: Any) -> PhoneNumbers:
    if raw is None or raw == [] or raw == {}:
        return PhoneNumbers([])
    if isinstance(raw, PhoneNumbers):
        return raw
    return PhoneNumbers.model_validate(raw)


def validate_phone_numbers_for_storage(raw: Any) -> list[dict[str, Any]]:
    return parse_phone_numbers(raw).to_json_list()


def normalize_phone_numbers(raw: Any) -> list[dict[str, Any]]:
    """Merge/validate stored JSON for API reads; empty on invalid legacy data."""
    try:
        return parse_phone_numbers(raw).to_json_list()
    except Exception:
        return []
