"""Extraction schemas for operational PLD documents (DOC-06, DOC-08..18)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from api.compliance.document_extraction.provenance import ProvenanceMixin


class ReformaCambioExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    acto_type: str | None = Field(default=None, description="REF-tipo_acto")
    acto_date: str | None = Field(default=None, description="REF-fecha_acto")
    relevant_changes: str | None = Field(
        default=None, description="REF-cambios_relevantes"
    )
    later_shareholders: str | None = Field(
        default=None, description="REF-socios_posteriores"
    )


class ReformaEstatutosExtraction(ProvenanceMixin):
    """DOC-06 Reformas estatutarias y actas de asamblea."""

    model_config = ConfigDict(extra="ignore")

    legal_name: str | None = None
    acts: list[ReformaCambioExtraction] = Field(default_factory=list)


class AccionistaTitularExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, description="ACC-titular_nombre")
    person_kind: str | None = Field(default=None, description="ACC-titular_tipo")
    rfc_or_curp: str | None = Field(default=None, description="ACC-rfc_curp")
    ownership_percentage: str | None = Field(
        default=None, description="ACC-participacion_pct"
    )
    shares_or_parts: str | None = Field(default=None, description="ACC-acciones_partes")
    control_type: str | None = Field(default=None, description="ACC-control_tipo")


class AccionistaLibroExtraction(ProvenanceMixin):
    """DOC-08 Libro de registro de acciones o partes sociales."""

    model_config = ConfigDict(extra="ignore")

    cutoff_date: str | None = Field(default=None, description="ACC-fecha_corte")
    holders: list[AccionistaTitularExtraction] = Field(default_factory=list)


class BeneficiarioControladorRow(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = Field(default=None, description="BC-persona_nombre")
    rfc_or_curp: str | None = Field(default=None, description="BC-rfc_curp")
    date_of_birth: str | None = Field(default=None, description="BC-fecha_nacimiento")
    nationality_residence: str | None = Field(
        default=None, description="BC-nacionalidad_residencia"
    )
    ownership_percentage: str | None = Field(
        default=None, description="BC-participacion_pct"
    )
    control_means: str | None = Field(default=None, description="BC-medio_control")


class BeneficiarioControladorDocExtraction(ProvenanceMixin):
    """DOC-09 Declaracion de beneficiario controlador."""

    model_config = ConfigDict(extra="ignore")

    declaration_date: str | None = Field(
        default=None, description="BC-declaracion_fecha"
    )
    signed: bool | None = Field(default=None, description="BC-declaracion_firmada")
    beneficiaries: list[BeneficiarioControladorRow] = Field(default_factory=list)


class ContratoExtraction(ProvenanceMixin):
    """DOC-10 Contrato, orden de servicio o propuesta aceptada."""

    model_config = ConfigDict(extra="ignore")

    document_type: str | None = Field(default=None, description="CON-tipo_documento")
    parties: str | None = Field(default=None, description="CON-partes")
    signatories: str | None = Field(default=None, description="CON-firmantes")
    purpose: str | None = Field(default=None, description="CON-objeto")
    start_date: str | None = Field(default=None, description="CON-fecha_inicio")
    end_date: str | None = Field(default=None, description="CON-fecha_fin")
    amount: str | None = Field(default=None, description="CON-monto")
    currency: str | None = Field(default=None, description="CON-moneda")
    payment_terms: str | None = Field(default=None, description="CON-forma_pago")


class CfdiConceptoExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    description: str | None = None
    quantity: str | None = None
    unit: str | None = None
    amount: str | None = None


class CfdiExtraction(ProvenanceMixin):
    """DOC-11 CFDI."""

    model_config = ConfigDict(extra="ignore")

    uuid: str | None = Field(default=None, description="CFDI-uuid")
    voucher_type: str | None = Field(default=None, description="CFDI-tipo_comprobante")
    issued_at: str | None = Field(default=None, description="CFDI-fecha_emision")
    issuer_rfc: str | None = Field(default=None, description="CFDI-rfc_emisor")
    issuer_name: str | None = Field(default=None, description="CFDI-nombre_emisor")
    receiver_rfc: str | None = Field(default=None, description="CFDI-rfc_receptor")
    receiver_name: str | None = Field(default=None, description="CFDI-nombre_receptor")
    concepts: list[CfdiConceptoExtraction] = Field(
        default_factory=list, description="CFDI-conceptos"
    )
    subtotal: str | None = Field(default=None, description="CFDI-subtotal")
    taxes: str | None = Field(default=None, description="CFDI-impuestos")
    total: str | None = Field(default=None, description="CFDI-total")
    currency: str | None = Field(default=None, description="CFDI-moneda")
    payment_method: str | None = Field(default=None, description="CFDI-metodo_pago")
    payment_form: str | None = Field(default=None, description="CFDI-forma_pago")


class EvidenciaMaterialidadExtraction(ProvenanceMixin):
    """DOC-12 Evidencia de materialidad."""

    model_config = ConfigDict(extra="ignore")

    evidence_type: str | None = Field(default=None, description="MAT-tipo_evidencia")
    evidence_date: str | None = Field(default=None, description="MAT-fecha_evidencia")
    description: str | None = Field(default=None, description="MAT-descripcion")
    service_period: str | None = Field(default=None, description="MAT-periodo_servicio")
    responsible: str | None = Field(default=None, description="MAT-responsable")


class MovimientoBancarioExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    date: str | None = None
    concept: str | None = None
    amount: str | None = None
    counterpart: str | None = None
    reference: str | None = None


class CaratulaBancariaExtraction(ProvenanceMixin):
    """DOC-13 Caratula de cuenta o estado de cuenta bancario."""

    model_config = ConfigDict(extra="ignore")

    holder: str | None = Field(default=None, description="BAN-titular")
    bank: str | None = Field(default=None, description="BAN-banco")
    bank_country: str | None = Field(default=None, description="BAN-pais_banco")
    account_number: str | None = Field(default=None, description="BAN-cuenta")
    clabe_or_iban: str | None = Field(default=None, description="BAN-clabe_iban")
    currency: str | None = Field(default=None, description="BAN-moneda")
    period_start: str | None = Field(default=None, description="BAN-periodo_inicio")
    period_end: str | None = Field(default=None, description="BAN-periodo_fin")
    relevant_movements: list[MovimientoBancarioExtraction] = Field(
        default_factory=list, description="BAN-movimientos_relevantes"
    )


class ComprobantePagoExtraction(ProvenanceMixin):
    """DOC-14 Comprobante de transferencia o pago."""

    model_config = ConfigDict(extra="ignore")

    paid_at: str | None = Field(default=None, description="PAGO-fecha")
    amount: str | None = Field(default=None, description="PAGO-monto")
    currency: str | None = Field(default=None, description="PAGO-moneda")
    originator: str | None = Field(default=None, description="PAGO-ordenante")
    beneficiary: str | None = Field(default=None, description="PAGO-beneficiario")
    source_account: str | None = Field(default=None, description="PAGO-cuenta_origen")
    destination_account: str | None = Field(
        default=None, description="PAGO-cuenta_destino"
    )
    reference: str | None = Field(default=None, description="PAGO-referencia")


class KycCuestionarioExtraction(ProvenanceMixin):
    """DOC-15 Cuestionario KYC o perfil transaccional."""

    model_config = ConfigDict(extra="ignore")

    questionnaire_date: str | None = Field(
        default=None, description="KYC-fecha_cuestionario"
    )
    declared_activity: str | None = Field(
        default=None, description="KYC-actividad_declarada"
    )
    resource_origin: str | None = Field(default=None, description="KYC-origen_recursos")
    resource_destination: str | None = Field(
        default=None, description="KYC-destino_recursos"
    )
    estimated_amount: str | None = Field(default=None, description="KYC-monto_estimado")
    frequency: str | None = Field(default=None, description="KYC-frecuencia")
    related_countries: str | None = Field(
        default=None, description="KYC-paises_relacionados"
    )
    pep_declared: str | None = Field(default=None, description="KYC-pep_declarado")


class CedulaFt01Extraction(ProvenanceMixin):
    """DOC-16 Cedula FT-01 Determinacion de Alcance y Sujecion."""

    model_config = ConfigDict(extra="ignore")

    folio: str | None = Field(default=None, description="FT01-folio")
    legal_name: str | None = Field(default=None, description="FT01-persona_moral")
    rfc: str | None = Field(default=None, description="FT01-rfc")
    issued_at: str | None = Field(default=None, description="FT01-fecha")
    real_operation: str | None = Field(default=None, description="FT01-operacion_real")
    product_or_service: str | None = Field(
        default=None, description="FT01-producto_servicio"
    )
    who_contracts: str | None = Field(default=None, description="FT01-quien_contrata")
    who_delivers_funds: str | None = Field(
        default=None, description="FT01-quien_entrega_recursos"
    )
    who_receives_funds: str | None = Field(
        default=None, description="FT01-quien_recibe_recursos"
    )
    on_behalf_of: str | None = Field(
        default=None, description="FT01-por_cuenta_de_quien"
    )
    individual_amount: str | None = Field(
        default=None, description="FT01-monto_individual"
    )
    frequency: str | None = Field(default=None, description="FT01-frecuencia")
    accumulated_amount: str | None = Field(
        default=None, description="FT01-monto_acumulado"
    )
    countries_or_states: str | None = Field(
        default=None, description="FT01-paises_estados"
    )
    payment_form: str | None = Field(default=None, description="FT01-forma_pago")
    documentary_sources: str | None = Field(
        default=None, description="FT01-fuentes_documentales"
    )
    vulnerable_activity: str | None = Field(
        default=None, description="FT01-actividad_vulnerable"
    )
    threshold: str | None = Field(default=None, description="FT01-umbral")
    subjection_conclusion: str | None = Field(
        default=None, description="FT01-conclusion_sujecion"
    )


class FichaFt02Extraction(ProvenanceMixin):
    """DOC-17 Ficha FT-02 Tecnica del Modelo."""

    model_config = ConfigDict(extra="ignore")

    nombre_modelo: str | None = Field(default=None, description="FT02-nombre_modelo")
    codigo_modelo: str | None = Field(default=None, description="FT02-codigo_modelo")
    version: str | None = Field(default=None, description="FT02-version")
    owner: str | None = Field(default=None, description="FT02-propietario")
    technical_owner: str | None = Field(
        default=None, description="FT02-responsable_tecnico"
    )
    approval_date: str | None = Field(default=None, description="FT02-fecha_aprobacion")
    next_review_date: str | None = Field(
        default=None, description="FT02-proxima_revision"
    )
    repository: str | None = Field(default=None, description="FT02-sistema_repositorio")
    result_matrices: str | None = Field(
        default=None, description="FT02-matrices_resultados"
    )
    change_control: str | None = Field(default=None, description="FT02-control_cambios")


class ReporteRi01Extraction(ProvenanceMixin):
    """DOC-18 Reporte RI-01 Integral."""

    model_config = ConfigDict(extra="ignore")

    folio: str | None = Field(default=None, description="RI01-folio")
    client_or_user: str | None = Field(default=None, description="RI01-cliente_usuario")
    rfc: str | None = Field(default=None, description="RI01-rfc")
    vulnerable_activity: str | None = Field(
        default=None, description="RI01-actividad_vulnerable"
    )
    incorporated_at: str | None = Field(
        default=None, description="RI01-fecha_incorporacion"
    )
    period_evaluated: str | None = Field(
        default=None, description="RI01-periodo_evaluado"
    )
    report_type: str | None = Field(default=None, description="RI01-tipo_reporte")
    analyst: str | None = Field(default=None, description="RI01-analista")
    reviewer: str | None = Field(default=None, description="RI01-revisor")
    authorizer: str | None = Field(default=None, description="RI01-autorizador")
    matrix_results: str | None = Field(
        default=None, description="RI01-resultados_matrices"
    )
    beneficial_owner: str | None = Field(
        default=None, description="RI01-beneficiario_controlador"
    )
    expedient_status: str | None = Field(
        default=None, description="RI01-estado_expediente"
    )
    transactional_profile: str | None = Field(
        default=None, description="RI01-perfil_transaccional"
    )
    alerts: str | None = Field(default=None, description="RI01-alertas")
    applied_controls: str | None = Field(
        default=None, description="RI01-controles_aplicados"
    )
    decision: str | None = Field(default=None, description="RI01-decision")
