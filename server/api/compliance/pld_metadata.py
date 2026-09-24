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
    email: str | None = None


class LegalRepresentativeData(BaseModel):
    model_config = ConfigDict(extra="ignore")

    given_names: str | None = None
    surnames: str | None = None
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
    surnames: str | None = None
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
            surnames = (self.surnames or "").strip() or " ".join(
                part.strip()
                for part in (self.paternal_surname, self.maternal_surname)
                if part and part.strip()
            )
            parts = [self.given_names, surnames]
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


def _filled(value: str | None) -> bool:
    return bool(value and str(value).strip())


def _email_ok(value: str | None) -> bool:
    text = (value or "").strip()
    return "@" in text and "." in text.split("@")[-1]


def _joined_surnames(
    surnames: str | None,
    paternal: str | None = None,
    maternal: str | None = None,
) -> str:
    if _filled(surnames):
        return surnames.strip()
    return " ".join(
        part.strip() for part in (paternal, maternal) if part and part.strip()
    )


def _address_complete(address: AddressData | None) -> bool:
    if address is None:
        return False
    return all(
        _filled(getattr(address, field))
        for field in (
            "country",
            "postal_code",
            "state",
            "municipality",
            "city",
            "neighborhood",
            "street",
            "exterior_number",
        )
    )


def _id_complete(identification: IdentificationData | None) -> bool:
    return bool(
        identification
        and _filled(identification.document_type)
        and _filled(identification.document_number)
    )


def identification_is_complete(person_type: str, metadata: dict | None) -> bool:
    """True when required identification fields are present (documents can unlock)."""
    if not isinstance(metadata, dict) or not metadata:
        return False
    if person_type == "persona_fisica":
        data = PersonaFisicaMetadata.model_validate(metadata)
        if not _filled(data.given_names):
            return False
        if not _joined_surnames(
            data.surnames, data.paternal_surname, data.maternal_surname
        ):
            return False
        if not _filled(data.date_of_birth) or not _filled(data.country_of_birth):
            return False
        nationality = (data.nationality or "").strip() or "MX"
        if nationality == "MX" and (not _filled(data.rfc) or not _filled(data.curp)):
            return False
        if not _filled(data.economic_activity):
            return False
        if not _address_complete(data.address) or not _id_complete(data.identification):
            return False
        if not data.is_own_controller:
            name = data.controller.name if data.controller else ""
            if not _filled(name):
                return False
            email = data.controller.email if data.controller else ""
            if not _email_ok(email):
                return False
        return True
    if person_type == "persona_moral":
        data = PersonaMoralMetadata.model_validate(metadata)
        if not _filled(data.legal_name) or not _filled(data.constitution_date):
            return False
        if not _filled(data.rfc) or not _filled(data.economic_activity):
            return False
        if not _address_complete(data.address):
            return False
        representative = data.representative
        if representative is None:
            return False
        if not _filled(representative.given_names):
            return False
        if not _joined_surnames(
            representative.surnames,
            representative.paternal_surname,
            representative.maternal_surname,
        ):
            return False
        if not _id_complete(representative.identification):
            return False
        if not any(_filled(item.name) for item in data.controllers):
            return False
        if not all(
            _email_ok(item.email) for item in data.controllers if _filled(item.name)
        ):
            return False
        return True
    return False


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
