"""Pydantic payloads extracted from PLD identification documents."""

from __future__ import annotations

from typing import Literal, TypeAlias, overload

from pydantic import BaseModel, ConfigDict, Field

from api.compliance.document_extraction.operational_schemas import (
    AccionistaLibroExtraction,
    ActaNacimientoExtraction,
    BeneficiarioControladorDocExtraction,
    CaratulaBancariaExtraction,
    CedulaFt01Extraction,
    CfdiExtraction,
    ClarificationExtraction,
    ComprobantePagoExtraction,
    ContratoExtraction,
    CurpSociosExtraction,
    EvidenciaMaterialidadExtraction,
    FichaFt02Extraction,
    KycCuestionarioExtraction,
    OrganigramaExtraction,
    ReformaEstatutosExtraction,
    ReporteRi01Extraction,
)
from api.compliance.document_extraction.provenance import FieldProvenance, ProvenanceMixin


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


class OfficialIdExtraction(ProvenanceMixin):
    """DOC-02 identificacion oficial vigente."""

    model_config = ConfigDict(extra="ignore")

    document_subtype: str | None = Field(
        default=None,
        description="ID-tipo: ine, passport, cedula, or other",
    )
    full_name: str | None = Field(default=None, description="ID-nombre_completo")
    given_names: str | None = None
    surnames: str | None = None
    curp: str | None = None
    date_of_birth: str | None = Field(default=None, description="ID-fecha_nacimiento")
    sex: str | None = Field(default=None, description="ID-sexo")
    nationality: str | None = Field(default=None, description="ID-nacionalidad")
    address_text: str | None = Field(default=None, description="ID-domicilio")
    address: AddressExtraction | None = None
    document_number: str | None = Field(
        default=None,
        description="ID-folio_clave: folio, clave de elector, pasaporte u equivalente",
    )
    cic: str | None = None
    ocr_line: str | None = None
    citizen_identifier: str | None = None
    issue_date: str | None = Field(default=None, description="ID-fecha_expedicion")
    validity_year: str | None = None
    mrz: str | None = None
    expiry_date: str | None = Field(default=None, description="ID-fecha_vencimiento")
    issuing_country: str | None = None
    photo_present: bool | None = None
    signature_present: bool | None = None
    expired_or_unreadable: bool | None = None


class CurpExtraction(ProvenanceMixin):
    """DOC-03 CURP o constancia CURP."""

    model_config = ConfigDict(extra="ignore")

    curp: str | None = Field(default=None, description="CURP-curp")
    full_name: str | None = Field(default=None, description="CURP-nombre_completo")
    given_names: str | None = None
    surnames: str | None = None
    date_of_birth: str | None = Field(default=None, description="CURP-fecha_nacimiento")
    sex: str | None = Field(default=None, description="CURP-sexo")
    entidad_nacimiento: str | None = Field(
        default=None, description="CURP-entidad_registro"
    )
    folio: str | None = None


class EconomicActivityExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    percentage: str | None = None
    start_date: str | None = None


class ConstanciaFiscalExtraction(ProvenanceMixin):
    """DOC-01 Constancia de Situacion Fiscal."""

    model_config = ConfigDict(extra="ignore")

    document_variant: str | None = Field(
        default=None,
        description="constancia_situacion_fiscal or cedula_datos_fiscales",
    )
    person_kind: str | None = Field(
        default=None, description="CSF-tipo_persona: fisica or moral"
    )
    rfc: str | None = Field(default=None, description="CSF-rfc")
    legal_name_or_full_name: str | None = Field(
        default=None, description="CSF-nombre_razon_social"
    )
    curp: str | None = None
    id_cif: str | None = None
    issued_at: str | None = Field(default=None, description="CSF-fecha_emision")
    operations_start_date: str | None = Field(
        default=None, description="CSF-fecha_inicio_operaciones"
    )
    padron_status: str | None = Field(default=None, description="CSF-estatus_padron")
    regimen_capital: str | None = None
    tax_address: AddressExtraction | None = Field(
        default=None, description="CSF-domicilio_fiscal"
    )
    postal_code: str | None = Field(default=None, description="CSF-cp_fiscal")
    economic_activities: list[EconomicActivityExtraction] = Field(
        default_factory=list,
        description="CSF-actividades_economicas",
    )
    tax_regimes: list[str] = Field(
        default_factory=list, description="CSF-regimen_fiscal"
    )
    legal_representative_name: str | None = None


class ComprobanteDomicilioExtraction(ProvenanceMixin):
    """DOC-04 Comprobante de domicilio."""

    model_config = ConfigDict(extra="ignore")

    issuer: str | None = Field(
        default=None,
        description="cfe, telmex, izzi, predial, bank, or other",
    )
    comprobante_type: str | None = Field(
        default=None,
        description="DOM-tipo_comprobante: luz, agua, predial, telefono, estado de cuenta u otro",
    )
    account_holder_name: str | None = Field(default=None, description="DOM-titular")
    service_address: AddressExtraction | None = Field(
        default=None, description="DOM-domicilio"
    )
    issue_or_period_date: str | None = Field(
        default=None, description="DOM-fecha_emision"
    )
    account_reference: str | None = Field(
        default=None, description="DOM-cuenta_referencia"
    )
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
    entidad_federativa: str | None = None
    escritura_number: str | None = None
    volume: str | None = None


class GrantedPowerExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    attorney_name: str | None = None
    powers_text: str | None = None


class ActaConstitutivaExtraction(ProvenanceMixin):
    """DOC-05 Acta constitutiva y estatutos vigentes."""

    model_config = ConfigDict(extra="ignore")

    legal_name: str | None = Field(
        default=None, description="ACTA-denominacion_social"
    )
    entity_type: str | None = Field(default=None, description="ACTA-tipo_societario")
    constitution_date: str | None = Field(
        default=None, description="ACTA-fecha_constitucion"
    )
    rfc: str | None = Field(default=None, description="ACTA-rfc")
    duration: str | None = None
    corporate_purpose: str | None = Field(default=None, description="ACTA-objeto_social")
    share_capital_amount: str | None = None
    share_capital_currency: str | None = None
    share_capital_kind: str | None = Field(
        default=None, description="fixed, variable, or mixed"
    )
    capital_fijo: str | None = Field(default=None, description="ACTA-capital_fijo")
    capital_variable: str | None = Field(
        default=None, description="ACTA-capital_variable"
    )
    notary: NotaryExtraction | None = None
    folio_mercantil: str | None = Field(default=None, description="ACTA-folio_mercantil")
    registered_address: AddressExtraction | None = None
    shareholders: list[ShareholderExtraction] = Field(
        default_factory=list, description="ACTA-socios_constitucion"
    )
    administrators: list[AdministratorExtraction] = Field(
        default_factory=list, description="ACTA-administracion"
    )
    granted_powers: list[GrantedPowerExtraction] = Field(default_factory=list)
    ownership_as_of: str | None = None
    ownership_may_be_stale: bool | None = True


class PoderExtraction(ProvenanceMixin):
    """DOC-07 Poder notarial."""

    model_config = ConfigDict(extra="ignore")

    grantor_legal_name: str | None = Field(default=None, description="POD-poderdante")
    attorney_name: str | None = Field(default=None, description="POD-apoderado_nombre")
    escritura_number: str | None = None
    notary: NotaryExtraction | None = None
    instrumento_notarial: str | None = Field(
        default=None,
        description="POD-instrumento_notarial: escritura, notario y formalizacion",
    )
    granted_at: str | None = Field(default=None, description="POD-fecha")
    administration: bool | None = None
    dominio: bool | None = None
    pleitos_y_cobranzas: bool | None = None
    powers_other: str | None = None
    facultades: str | None = Field(default=None, description="POD-facultades")
    limits: str | None = None
    revoked_or_expired: bool | None = None
    revocacion_consta: str | None = Field(
        default=None,
        description="POD-revocacion_consta: revocacion, vigencia o ausencia de evidencia",
    )


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
    "acta_nacimiento",
    "organigrama",
    "curp_representante",
    "curp_socios",
    "matriz_accionaria",
    "reforma_estatutos",
    "libro_acciones",
    "declaracion_bc",
    "contrato",
    "cfdi",
    "evidencia_materialidad",
    "caratula_bancaria",
    "comprobante_pago",
    "cuestionario_kyc",
    "cedula_ft01",
    "ficha_ft02",
    "reporte_ri01",
    "clarification",
]

PldExtraction: TypeAlias = (
    OfficialIdExtraction
    | CurpExtraction
    | ConstanciaFiscalExtraction
    | ComprobanteDomicilioExtraction
    | ActaConstitutivaExtraction
    | PoderExtraction
    | ActaNacimientoExtraction
    | OrganigramaExtraction
    | CurpSociosExtraction
    | ReformaEstatutosExtraction
    | AccionistaLibroExtraction
    | BeneficiarioControladorDocExtraction
    | ContratoExtraction
    | CfdiExtraction
    | EvidenciaMaterialidadExtraction
    | CaratulaBancariaExtraction
    | ComprobantePagoExtraction
    | KycCuestionarioExtraction
    | CedulaFt01Extraction
    | FichaFt02Extraction
    | ReporteRi01Extraction
    | ClarificationExtraction
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
    "acta_nacimiento": ActaNacimientoExtraction,
    "organigrama": OrganigramaExtraction,
    "curp_representante": CurpExtraction,
    "curp_socios": CurpSociosExtraction,
    "matriz_accionaria": AccionistaLibroExtraction,
    "reforma_estatutos": ReformaEstatutosExtraction,
    "libro_acciones": AccionistaLibroExtraction,
    "declaracion_bc": BeneficiarioControladorDocExtraction,
    "contrato": ContratoExtraction,
    "cfdi": CfdiExtraction,
    "evidencia_materialidad": EvidenciaMaterialidadExtraction,
    "caratula_bancaria": CaratulaBancariaExtraction,
    "comprobante_pago": ComprobantePagoExtraction,
    "cuestionario_kyc": KycCuestionarioExtraction,
    "cedula_ft01": CedulaFt01Extraction,
    "ficha_ft02": FichaFt02Extraction,
    "reporte_ri01": ReporteRi01Extraction,
    "clarification": ClarificationExtraction,
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


__all__ = [
    "AddressExtraction",
    "AdministratorExtraction",
    "ActaConstitutivaExtraction",
    "ComprobanteDomicilioExtraction",
    "ConstanciaFiscalExtraction",
    "CurpExtraction",
    "EconomicActivityExtraction",
    "FieldProvenance",
    "GrantedPowerExtraction",
    "NotaryExtraction",
    "OFFICIAL_ID_KINDS",
    "OfficialIdExtraction",
    "PldDocumentKind",
    "PldExtraction",
    "PoderExtraction",
    "SCHEMA_BY_KIND",
    "ShareholderExtraction",
    "schema_for_kind",
]
