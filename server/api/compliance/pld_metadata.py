"""Validated PLD entity metadata (no document bytes)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic import ValidationError as PydanticValidationError


class AddressData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    street: str | None = None
    exterior_number: str | None = None
    interior_number: str | None = None
    neighborhood: str | None = None
    municipality: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


class IdentificationData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_type: str | None = None
    issuing_authority: str | None = None
    document_number: str | None = None


class ControllerBeneficiary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    ownership_percentage: str | None = None
    rfc: str | None = None


class LegalRepresentativeData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    given_names: str | None = None
    paternal_surname: str | None = None
    maternal_surname: str | None = None
    date_of_birth: str | None = None
    rfc: str | None = None
    curp: str | None = None
    identification: IdentificationData | None = None


class PersonaFisicaMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 2
    given_names: str | None = None
    paternal_surname: str | None = None
    maternal_surname: str | None = None
    name: str | None = None
    date_of_birth: str | None = None
    country_of_birth: str | None = None
    nationality: str | None = None
    curp: str | None = None
    rfc: str | None = None
    economic_activity: str | None = None
    phone: str | None = None
    email: str | None = None
    address: AddressData | None = None
    identification: IdentificationData | None = None
    is_own_controller: bool = True
    controller: ControllerBeneficiary | None = None

    @model_validator(mode="after")
    def fill_display_name(self):
        if not (self.name or "").strip():
            parts = [self.given_names, self.paternal_surname, self.maternal_surname]
            joined = " ".join(part.strip() for part in parts if part and part.strip())
            self.name = joined or None
        return self


class PersonaMoralMetadata(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = 2
    legal_name: str | None = None
    constitution_date: str | None = None
    nationality: str | None = None
    rfc: str | None = None
    economic_activity: str | None = None
    phone: str | None = None
    email: str | None = None
    address: AddressData | None = None
    representative: LegalRepresentativeData | None = None
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
