"""File integrity and META block attached after LLM extraction."""

from __future__ import annotations

import hashlib
from typing import Any


def sha256_of_uploaded_file(uploaded) -> str:
    hasher = hashlib.sha256()
    for chunk in uploaded.chunks():
        hasher.update(chunk)
    if hasattr(uploaded, "seek"):
        uploaded.seek(0)
    return hasher.hexdigest()


def extraction_meta(doc, payload: dict[str, Any]) -> dict[str, Any]:
    provenances = payload.get("provenances") if isinstance(payload, dict) else None
    confidences = []
    if isinstance(provenances, list):
        for item in provenances:
            if not isinstance(item, dict):
                continue
            value = item.get("confianza_extraccion")
            if isinstance(value, (int, float)):
                confidences.append(float(value))
    overall = round(sum(confidences) / len(confidences), 4) if confidences else None
    pages = []
    if isinstance(provenances, list):
        for item in provenances:
            if not isinstance(item, dict):
                continue
            page = item.get("pagina_origen")
            if page:
                pages.append(str(page))
    unique_pages = sorted(set(pages))
    return {
        "document_id": str(doc.id),
        "nombre_archivo": doc.original_filename or "",
        "hash": getattr(doc, "file_sha256", "") or "",
        "fecha_carga": doc.created_at.isoformat() if doc.created_at else None,
        "paginas_origen": unique_pages,
        "confianza_extraccion": overall,
    }
