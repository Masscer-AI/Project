"""Pydantic payloads extracted from PLD identification documents."""

from __future__ import annotations

from typing import Literal, TypeAlias, overload

from pydantic import BaseModel, ConfigDict, Field


class AddressExtraction(BaseModel):
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
    raw_text: str | None = None


class OfficialIdExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_subtype: str | None = Field(
        default=None,
        description="ine, passport, cedula, or other",
    )
    full_name: str | None = None
    given_names: str | None = None
    surnames: str | None = None
    curp: str | None = None
    date_of_birth: str | None = None
    sex: str | None = None
    nationality: str | None = None
    address_text: str | None = None
    address: AddressExtraction | None = None
    document_number: str | None = None
    cic: str | None = None
    ocr_line: str | None = None
    citizen_identifier: str | None = None
    validity_year: str | None = None
    mrz: str | None = None
    expiry_date: str | None = None
    issuing_country: str | None = None
    photo_present: bool | None = None
    signature_present: bool | None = None
    expired_or_unreadable: bool | None = None


class CurpExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    curp: str | None = None
    given_names: str | None = None
    surnames: str | None = None
    date_of_birth: str | None = None
    sex: str | None = None
    entidad_nacimiento: str | None = None
    folio: str | None = None


class EconomicActivityExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    percentage: str | None = None
    start_date: str | None = None


class ConstanciaFiscalExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    document_variant: str | None = Field(
        default=None,
        description="constancia_situacion_fiscal or cedula_datos_fiscales",
    )
    person_kind: str | None = Field(
        default=None, description="fisica or moral"
    )
    rfc: str | None = None
    legal_name_or_full_name: str | None = None
    curp: str | None = None
    id_cif: str | None = None
    issued_at: str | None = None
    padron_status: str | None = None
    regimen_capital: str | None = None
    tax_address: AddressExtraction | None = None
    economic_activities: list[EconomicActivityExtraction] = Field(
        default_factory=list
    )
    tax_regimes: list[str] = Field(default_factory=list)
    legal_representative_name: str | None = None


class ComprobanteDomicilioExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    issuer: str | None = Field(
        default=None,
        description="cfe, telmex, izzi, predial, bank, or other",
    )
    account_holder_name: str | None = None
    service_address: AddressExtraction | None = None
    issue_or_period_date: str | None = None
    older_than_three_months: bool | None = None
    name_matches_client_hint: bool | None = None


class ShareholderExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    person_kind: str | None = Field(
        default=None, description="fisica or moral"
    )
    nationality: str | None = None
    rfc: str | None = None
    curp: str | None = None
    shares_or_parts: str | None = None
    ownership_percentage: str | None = None
    contribution: str | None = None


class AdministratorExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    role: str | None = Field(
        default=None, description="administrador_unico or consejo"
    )


class NotaryExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    notaria_number: str | None = None
    city: str | None = None
    escritura_number: str | None = None
    volume: str | None = None


class GrantedPowerExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    attorney_name: str | None = None
    powers_text: str | None = None


class ActaConstitutivaExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    legal_name: str | None = None
    entity_type: str | None = None
    constitution_date: str | None = None
    duration: str | None = None
    corporate_purpose: str | None = None
    share_capital_amount: str | None = None
    share_capital_currency: str | None = None
    share_capital_kind: str | None = Field(
        default=None, description="fixed, variable, or mixed"
    )
    notary: NotaryExtraction | None = None
    folio_mercantil: str | None = None
    registered_address: AddressExtraction | None = None
    shareholders: list[ShareholderExtraction] = Field(default_factory=list)
    administrators: list[AdministratorExtraction] = Field(default_factory=list)
    granted_powers: list[GrantedPowerExtraction] = Field(default_factory=list)
    ownership_as_of: str | None = None
    ownership_may_be_stale: bool | None = True


class PoderExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    grantor_legal_name: str | None = None
    attorney_name: str | None = None
    escritura_number: str | None = None
    notary: NotaryExtraction | None = None
    granted_at: str | None = None
    administration: bool | None = None
    dominio: bool | None = None
    pleitos_y_cobranzas: bool | None = None
    powers_other: str | None = None
    limits: str | None = None
    revoked_or_expired: bool | None = None


OFFICIAL_ID_KINDS = frozenset(
    {"official_id", "id_representante", "id_controlador"}
)

PldDocumentKind: TypeAlias = Literal[
    "official_id",
    "id_representante",
    "id_controlador",
    "curp",
    "constancia_fiscal",
    "comprobante_domicilio",
    "acta_constitutiva",
    "poder",
]

PldExtraction: TypeAlias = (
    OfficialIdExtraction
    | CurpExtraction
    | ConstanciaFiscalExtraction
    | ComprobanteDomicilioExtraction
    | ActaConstitutivaExtraction
    | PoderExtraction
)

SCHEMA_BY_KIND: dict[PldDocumentKind, type[PldExtraction]] = {
    "official_id": OfficialIdExtraction,
    "id_representante": OfficialIdExtraction,
    "id_controlador": OfficialIdExtraction,
    "curp": CurpExtraction,
    "constancia_fiscal": ConstanciaFiscalExtraction,
    "comprobante_domicilio": ComprobanteDomicilioExtraction,
    "acta_constitutiva": ActaConstitutivaExtraction,
    "poder": PoderExtraction,
}


@overload
def schema_for_kind(
    document_kind: Literal["official_id", "id_representante", "id_controlador"],
) -> type[OfficialIdExtraction]: ...


@overload
def schema_for_kind(document_kind: Literal["curp"]) -> type[CurpExtraction]: ...


@overload
def schema_for_kind(
    document_kind: Literal["constancia_fiscal"],
) -> type[ConstanciaFiscalExtraction]: ...


@overload
def schema_for_kind(
    document_kind: Literal["comprobante_domicilio"],
) -> type[ComprobanteDomicilioExtraction]: ...


@overload
def schema_for_kind(
    document_kind: Literal["acta_constitutiva"],
) -> type[ActaConstitutivaExtraction]: ...


@overload
def schema_for_kind(document_kind: Literal["poder"]) -> type[PoderExtraction]: ...


@overload
def schema_for_kind(document_kind: str) -> type[PldExtraction]: ...


def schema_for_kind(document_kind: str) -> type[PldExtraction]:
    schema = SCHEMA_BY_KIND.get(document_kind)  # type: ignore[arg-type]
    if schema is None:
        raise ValueError(f"Unknown document_kind '{document_kind}'")
    return schema
