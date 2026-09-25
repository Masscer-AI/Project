from __future__ import annotations

import os

import requests

from api.ai_layers.tools.generate_gamma_presentation import (
    _api_key,
    _download_export,
    _headers,
    _poll_generation,
    _raise_for_gamma_status,
    GAMMA_API_BASE,
)
from api.compliance.invites import entity_display_name
from api.compliance.packet.pdf import _paragraphs, build_identification_packet_pdf

DEFAULT_TEMPLATE_ID = "g_ss07hpbni8ilyhy"


def expediente_template_id() -> str:
    raw = (os.environ.get("GAMMA_EXPEDIENTE_TEMPLATE_ID") or "").strip()
    return raw or DEFAULT_TEMPLATE_ID


def _prompt(entity) -> str:
    body = "\n".join(_paragraphs(entity))
    return (
        "Fill this one-page identification expediente with the facts below. "
        "When an aclaracion corrects an earlier fact, use the aclaracion. "
        "Keep the template layout. Do not add or remove pages. Write in Spanish.\n\n"
        + body
    )


def render_identification_packet_pdf(entity) -> bytes:
    try:
        api_key = _api_key()
    except ValueError:
        return build_identification_packet_pdf(entity)
    name = entity_display_name(entity)
    title = f"Expediente de identificacion — {name}"[:500]
    resp = requests.post(
        f"{GAMMA_API_BASE}/generations/from-template",
        headers=_headers(api_key),
        json={
            "gammaId": expediente_template_id(),
            "prompt": _prompt(entity),
            "title": title,
            "exportAs": "pdf",
            "sharingOptions": {
                "workspaceAccess": "noAccess",
                "externalAccess": "noAccess",
            },
        },
        timeout=60,
    )
    _raise_for_gamma_status(resp, action="template generation create")
    generation_id = (resp.json() or {}).get("generationId")
    if not generation_id:
        raise ValueError("Gamma did not return a generationId.")
    status_data = _poll_generation(api_key, str(generation_id))
    export_url = (status_data.get("exportUrl") or "").strip()
    if not export_url:
        raise ValueError("Gamma template generation completed without an exportUrl.")
    return _download_export(export_url)
