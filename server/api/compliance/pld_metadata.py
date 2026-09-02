"""Validated PLD entity metadata (no document bytes)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationError as PydanticValidationError


class ControllerBeneficiary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    ownership_percentage: str | None = None
    rfc: str | None = None


class PersonaFisicaMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    name: str | None = None
    rfc: str | None = None
    economic_activity: str | None = None
    is_own_controller: bool = True
    controller: ControllerBeneficiary | None = None


class PersonaMoralMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 1
    legal_name: str | None = None
    rfc: str | None = None
    economic_activity: str | None = None
    controllers: list[ControllerBeneficiary] = Field(default_factory=list)


def normalize_pld_entity_metadata(person_type: str, raw) -> dict:
    """Return a dumped metadata dict, or raise ValueError."""
    if raw in (None, ""):
        return {}
    if not isinstance(raw, dict):
        raise ValueError("metadata must be a JSON object")
    if not raw:
        return {}
    if person_type == "persona_fisica":
        try:
            return PersonaFisicaMetadata.model_validate(raw).model_dump(mode="json")
        except PydanticValidationError as exc:
            raise ValueError(str(exc)) from exc
    if person_type == "persona_moral":
        try:
            return PersonaMoralMetadata.model_validate(raw).model_dump(mode="json")
        except PydanticValidationError as exc:
            raise ValueError(str(exc)) from exc
    raise ValueError(f"Unknown person_type '{person_type}'")
