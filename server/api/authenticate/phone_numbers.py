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

# Mexico: ITU E.164 is 52 + 10 national digits. WhatsApp/Meta still uses the
# legacy mobile insert "1" → 521 + 10 digits (13 total).
_MX_CC = "52"
_MX_META_PREFIX = "521"
_MX_NATIONAL_LEN = 10
_MX_E164_LEN = 12  # 52 + 10
_MX_META_LEN = 13  # 521 + 10


def _digits_only(value: str) -> str:
    return _DIGITS_RE.sub("", value or "")


def to_meta_whatsapp_digits(digits: str) -> str:
    """
    Normalize full international digits to Meta/WhatsApp form.

    Mexican ``52XXXXXXXXXX`` (12 digits) → ``521XXXXXXXXXX`` (13 digits).
    Already-Meta Mexican numbers and all other countries are unchanged.
    """
    d = _digits_only(digits)
    if not d:
        return d
    if d.startswith(_MX_META_PREFIX) and len(d) == _MX_META_LEN:
        return d
    if d.startswith(_MX_CC) and len(d) == _MX_E164_LEN:
        return _MX_META_PREFIX + d[len(_MX_CC) :]
    return d


def whatsapp_phone_match_keys(digits: str) -> set[str]:
    """
    Digit forms that identify the same WhatsApp user.

    For Mexico, include both Meta (``521…``) and plain E.164 (``52…``) so a
    profile saved as E.164 still matches inbound Meta webhooks.
    """
    d = _digits_only(digits)
    if not d:
        return set()
    keys = {d, to_meta_whatsapp_digits(d)}
    if d.startswith(_MX_META_PREFIX) and len(d) == _MX_META_LEN:
        keys.add(_MX_CC + d[len(_MX_META_PREFIX) :])
    return {k for k in keys if k}


def phones_match_whatsapp(left: str, right: str) -> bool:
    """True if two phone digit strings refer to the same WhatsApp identity."""
    left_keys = whatsapp_phone_match_keys(left)
    if not left_keys:
        return False
    return bool(left_keys & whatsapp_phone_match_keys(right))


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
    def normalize_mexico_to_meta_whatsapp(self) -> PhoneNumber:
        """
        Persist Mexican numbers in Meta/WhatsApp form automatically.

        Users typically enter ITU E.164 (``+52`` + 10 digits). Meta webhooks
        and Graph send use ``521`` + 10 digits, so we store that shape.
        """
        # country_code mistakenly set to 521 with 10-digit national
        if self.country_code == _MX_META_PREFIX and len(self.number) == _MX_NATIONAL_LEN:
            self.country_code = _MX_CC
            self.number = "1" + self.number
            return self

        if self.country_code != _MX_CC:
            return self

        # Plain E.164 national (10 digits) → insert Meta mobile "1"
        if len(self.number) == _MX_NATIONAL_LEN:
            self.number = "1" + self.number
            return self

        # Already Meta national (1 + 10 digits)
        if len(self.number) == _MX_NATIONAL_LEN + 1 and self.number.startswith("1"):
            return self

        return self

    @model_validator(mode="after")
    def validate_e164_length(self) -> PhoneNumber:
        # E.164 max is 15 digits including country code.
        # Meta Mexico (521 + 10) is 13 digits and still within the limit.
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

    def whatsapp_digits(self) -> str:
        """Digits in Meta/WhatsApp form (Mexico normalized)."""
        return to_meta_whatsapp_digits(self.e164_digits())

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
            # Canonical Meta form so MX E.164 and MX Meta count as duplicates.
            key = entry.whatsapp_digits()
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

    def as_whatsapp_match_set(self) -> set[str]:
        """All digit forms that should match these numbers on WhatsApp."""
        keys: set[str] = set()
        for entry in self.root:
            keys |= whatsapp_phone_match_keys(entry.e164_digits())
        return keys

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
