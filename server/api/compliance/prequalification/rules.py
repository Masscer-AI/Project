"""Machine-readable identification checklist derived from RCG Anexos 3/4."""

from __future__ import annotations

from api.compliance.prequalification.sources import LEGAL_SOURCES, RULESET_VERSION

# Each check is what Masscer requires before list screening. `source_ids` point to LEGAL_SOURCES.
IDENTIFICATION_RULES = {
    "version": RULESET_VERSION,
    "sources": LEGAL_SOURCES,
    "persona_fisica": {
        "declared": [
            {
                "id": "name",
                "fields": ["given_names", "surnames"],
                "source_ids": ["rcg"],
            },
            {
                "id": "birth",
                "fields": ["date_of_birth", "country_of_birth"],
                "source_ids": ["rcg"],
            },
            {
                "id": "nationality",
                "fields": ["nationality"],
                "source_ids": ["rcg"],
            },
            {
                "id": "rfc_curp_if_mx",
                "fields": ["rfc", "curp"],
                "when": "nationality is MX or empty",
                "source_ids": ["rcg"],
            },
            {
                "id": "occupation",
                "fields": ["economic_activity"],
                "source_ids": ["rcg", "lfpiorpi"],
            },
            {
                "id": "address",
                "fields": [
                    "address.country",
                    "address.postal_code",
                    "address.state",
                    "address.municipality",
                    "address.city",
                    "address.neighborhood",
                    "address.street",
                    "address.exterior_number",
                ],
                "source_ids": ["rcg"],
            },
            {
                "id": "official_id_data",
                "fields": ["identification.document_type", "identification.document_number"],
                "source_ids": ["rcg"],
            },
            {
                "id": "controller_if_not_self",
                "fields": ["controller.name"],
                "when": "is_own_controller is false",
                "source_ids": ["rcg"],
            },
        ],
        "documents": [
            {"kind": "official_id", "required": True, "source_ids": ["rcg"]},
            {"kind": "comprobante_domicilio", "required": True, "source_ids": ["rcg"]},
            {"kind": "curp", "required": True, "source_ids": ["rcg"]},
            {"kind": "constancia_fiscal", "required": True, "source_ids": ["rcg"]},
            {"kind": "cfdi", "required": True, "source_ids": ["rcg"]},
            {"kind": "acta_nacimiento", "required": False, "source_ids": ["rcg"]},
            {"kind": "organigrama", "required": False, "source_ids": ["rcg"]},
            {"kind": "id_controlador", "required_if": "is_own_controller is false", "source_ids": ["rcg"]},
        ],
        "quality": [
            {
                "id": "id_not_expired",
                "rule": "Official ID must be current; Anexo 3: if expired, expiry at presentation not older than two years, with photo.",
                "source_ids": ["rcg"],
            },
            {
                "id": "address_proof_max_3_months",
                "rule": "Proof of address issue/period date not older than three months.",
                "source_ids": ["rcg"],
            },
        ],
        "reconcile": [
            {"id": "rfc_vs_csf", "source_ids": ["rcg"]},
            {"id": "curp_vs_curp_doc", "source_ids": ["rcg"]},
            {"id": "name_vs_id", "source_ids": ["rcg"]},
            {"id": "address_vs_comprobante", "source_ids": ["rcg"]},
        ],
    },
    "persona_moral": {
        "declared": [
            {
                "id": "legal_name",
                "fields": ["legal_name", "constitution_date", "rfc", "economic_activity"],
                "source_ids": ["rcg"],
            },
            {"id": "address", "fields": ["address"], "source_ids": ["rcg"]},
            {
                "id": "representative",
                "fields": [
                    "representative.given_names",
                    "representative.surnames",
                    "representative.identification",
                ],
                "source_ids": ["rcg"],
            },
            {
                "id": "controllers",
                "fields": ["controllers[].name"],
                "source_ids": ["rcg"],
                "note": "Art. 23 Quinquies: 25% ownership, else control, else senior officer. Must be a natural person.",
            },
        ],
        "documents": [
            {"kind": "acta_constitutiva", "required": True, "source_ids": ["rcg"]},
            {"kind": "constancia_fiscal", "required": True, "source_ids": ["rcg"]},
            {"kind": "comprobante_domicilio", "required": True, "source_ids": ["rcg"]},
            {"kind": "id_representante", "required": True, "source_ids": ["rcg"]},
            {"kind": "curp_representante", "required": True, "source_ids": ["rcg"]},
            {"kind": "cfdi", "required": True, "source_ids": ["rcg"]},
            {"kind": "id_controlador", "required": True, "source_ids": ["rcg"]},
            {"kind": "poder", "required": False, "source_ids": ["rcg"]},
            {"kind": "curp_socios", "required": False, "source_ids": ["rcg"]},
            {"kind": "organigrama", "required": False, "source_ids": ["rcg"]},
            {"kind": "matriz_accionaria", "required": False, "source_ids": ["rcg"]},
        ],
        "quality": [
            {
                "id": "address_proof_max_3_months",
                "rule": "Proof of address issue/period date not older than three months.",
                "source_ids": ["rcg"],
            },
            {
                "id": "ownership_may_be_stale",
                "rule": "Acta shows ownership at constitution; warn if it may be stale versus declared controllers.",
                "source_ids": ["rcg"],
            },
        ],
        "reconcile": [
            {"id": "rfc_vs_csf", "source_ids": ["rcg"]},
            {"id": "legal_name_vs_acta_and_csf", "source_ids": ["rcg"]},
            {"id": "representative_vs_id", "source_ids": ["rcg"]},
            {"id": "controller_vs_acta_shareholders", "source_ids": ["rcg"]},
        ],
    },
    "out_of_scope_until_list_screening": [
        "PEP lists (Art. 23 Quater RCG / Acuerdo 115/2026)",
        "Listas negativas / SAT 69 / OFAC / ONU",
        "Risk matrix and traffic-light score",
    ],
}
