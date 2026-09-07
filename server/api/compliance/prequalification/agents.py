"""LLM review of identification completeness and consistency (not list screening)."""

from __future__ import annotations

import logging

from api.compliance.document_extraction.constants import PLD_EXTRACTION_MODEL_SLUG
from api.compliance.pld_document_slots import required_slots_extraction_ready
from api.compliance.prequalification.deterministic import (
    controller_names,
    deterministic_findings,
    verdict_from_findings,
)
from api.compliance.prequalification.pack import build_prequalification_packet
from api.compliance.prequalification.schemas import (
    PrequalFinding,
    PrequalificationResult,
)
from api.compliance.prequalification.sources import RULESET_VERSION

logger = logging.getLogger(__name__)

INSTRUCTIONS = """
Eres el agente de precalificacion de identificacion PLD de Masscer.
Tu unico trabajo es decidir si el expediente unico de identificacion esta completo
y consistente ANTES del cruce con listas (PEP, listas negativas) y ANTES de la
matriz de riesgo / semaforo.

Reglas:
- Evalua SOLO contra el objeto `rules` del paquete (Anexos 3/4 RCG, LFPIORPI).
- No inventes requisitos que no esten en `rules`.
- No consultes listas, no asignes semaforo, no declares PEP.
- Conserva todos los hallazgos deterministicos con severity blocker; puedes anadir
  warnings de conciliacion (nombres, domicilios, representante vs ID, socios vs
  beneficiario controlador).
- Nunca inventes RFC, CURP, fechas ni porcentajes.
- summary en espanol, breve, para la contraparte (sin jerga interna de scoring).
- source_ids solo de: lfpiorpi, reglamento, rcg, uif-portal.
""".strip()


def _merge_findings(
    base: list[PrequalFinding], extra: list[PrequalFinding]
) -> list[PrequalFinding]:
    seen = {(item.code, item.target, item.summary) for item in base}
    merged = list(base)
    for item in extra:
        key = (item.code, item.target, item.summary)
        if key in seen:
            continue
        seen.add(key)
        merged.append(item)
    return merged


def _billing(entity) -> tuple[int | None, object]:
    org = getattr(entity, "organization", None)
    owner_id = getattr(org, "owner_id", None) if org else None
    return owner_id, getattr(org, "id", None)


def run_prequalification(entity) -> PrequalificationResult:
    det = deterministic_findings(entity)
    ready, _reason = required_slots_extraction_ready(entity)
    if not ready:
        return PrequalificationResult(
            ruleset_version=RULESET_VERSION,
            verdict=verdict_from_findings(det),
            summary=(
                "Aun no se puede precalificar: faltan documentos obligatorios "
                "o la extraccion no ha terminado."
            ),
            findings=det,
            controllers=controller_names(entity),
        )

    packet = build_prequalification_packet(entity)
    billing_user_id, organization_id = _billing(entity)

    from api.ai_layers.agent_loop import AgentLoop

    loop = AgentLoop.create(
        provider="openai",
        tools=[],
        instructions=INSTRUCTIONS,
        model=PLD_EXTRACTION_MODEL_SLUG,
        output_schema=PrequalificationResult,
        max_iterations=2,
        repair_model=PLD_EXTRACTION_MODEL_SLUG,
    )
    result = loop.run(
        [
            {
                "role": "user",
                "content": (
                    "Precalifica este expediente de identificacion. "
                    "Devuelve JSON del schema. Paquete:\n"
                    + packet
                ),
            }
        ]
    )
    usage = result.usage or {}
    prompt_tokens = int(usage.get("prompt_tokens") or 0)
    completion_tokens = int(usage.get("completion_tokens") or 0)
    if billing_user_id and (prompt_tokens or completion_tokens):
        from api.consumption.actions import register_llm_interaction

        register_llm_interaction(
            billing_user_id,
            prompt_tokens,
            completion_tokens,
            PLD_EXTRACTION_MODEL_SLUG,
            organization_id=organization_id,
        )

    output = result.output
    if not isinstance(output, PrequalificationResult):
        raise ValueError("Prequalification did not return structured output")

    findings = _merge_findings(det, output.findings)
    verdict = verdict_from_findings(findings)
    controllers = output.controllers or controller_names(entity)
    summary = output.summary.strip() if output.summary else ""
    if not summary:
        if verdict == "blocked":
            summary = "Faltan datos o documentos obligatorios, o hay inconsistencias que impiden el cruce de listas."
        elif verdict == "needs_review":
            summary = "La identificacion esta integrada, con observaciones para revision humana."
        else:
            summary = "La identificacion esta completa y consistente para pasar al cruce de listas."
    return PrequalificationResult(
        ruleset_version=RULESET_VERSION,
        verdict=verdict,
        summary=summary,
        findings=findings,
        controllers=controllers,
        human_notes=output.human_notes,
    )
