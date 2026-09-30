"""100-point residual score from editable PLDMatrix rows."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from api.compliance.risk.activities import (
    activity_texts_for_entity,
    match_vulnerable_activity,
)
from api.compliance.risk.evaluate import (
    _controllers_missing,
    _finding_codes,
    _findings,
    _payload_dict,
)
from api.compliance.risk.catalog import classify_hit

_MATERIAL = frozenset(
    {"rfc_mismatch", "curp_mismatch", "controller_missing", "legal_name_mismatch"}
)
_SOFT = frozenset(
    {
        "id_expired_or_unreadable",
        "address_proof_stale",
        "acta_ownership_stale",
        "acta_extraction_thin",
    }
)


@lru_cache(maxsize=1)
def _cities() -> list[dict[str, Any]]:
    path = (
        Path(__file__).resolve().parent / "catalogs" / "city_security_index_2026.json"
    )
    return json.loads(path.read_text(encoding="utf-8")).get("cities") or []


def _fold(value: str) -> str:
    return " ".join(str(value or "").casefold().split())


def _city_index(entity) -> int | None:
    meta = _payload_dict(getattr(entity, "metadata", None))
    address = meta.get("address") if isinstance(meta.get("address"), dict) else {}
    parts = [
        str(address.get("city") or ""),
        str(address.get("municipality") or ""),
        str(address.get("state") or ""),
    ]
    blob = _fold(" ".join(parts))
    if not blob:
        return None
    best: tuple[int, int] | None = None
    for row in _cities():
        name = _fold(str(row.get("city") or ""))
        if not name:
            continue
        if name in blob or blob in name:
            score = int(row.get("index") or 0)
            if best is None or len(name) > best[0]:
                best = (len(name), score)
    return best[1] if best else None


def _docs(expedient) -> list[Any]:
    docs = getattr(expedient, "documents", None)
    if docs is None:
        return []
    if hasattr(docs, "all"):
        return list(docs.all())
    return list(docs)


def _cfdi_over_notice(entity, expedient) -> bool:
    match = match_vulnerable_activity(*activity_texts_for_entity(entity))
    if not match or match.get("notice_mxn") is None:
        return False
    limit = float(match["notice_mxn"])
    for doc in _docs(expedient):
        if getattr(doc, "document_kind", "") != "cfdi":
            continue
        payload = _payload_dict(getattr(doc, "extracted_payload", None))
        raw = payload.get("total")
        try:
            total = float(raw)
        except (TypeError, ValueError):
            continue
        if total > limit:
            return True
    return False


def _points() -> dict[str, float]:
    from api.compliance.models import PLDMatrix
    from api.compliance.pld_matrix import seed_pld_matrix

    seed_pld_matrix()
    return {row.slug: float(row.points) for row in PLDMatrix.objects.all()}


def _pt(table: dict[str, float], slug: str, fallback: float) -> float:
    return table.get(slug, fallback)


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, round(value, 1)))


def _color(total: float, table: dict[str, float]) -> str:
    if total >= _pt(table, "cutoff_red", 65):
        return "red"
    if total >= _pt(table, "cutoff_orange", 45):
        return "orange"
    if total >= _pt(table, "cutoff_yellow", 25):
        return "yellow"
    return "green"


def _share(rating: int, weight: float) -> float:
    return (max(0, min(4, rating)) / 4.0) * weight


def score_pld_matrix(entity, expedient) -> dict[str, Any]:
    table = _points()
    meta = _payload_dict(getattr(entity, "metadata", None))
    codes = _finding_codes(_findings(expedient))
    screening = _payload_dict(getattr(expedient, "screening_payload", None))
    hits = [item for item in (screening.get("hits") or []) if isinstance(item, dict)]
    klass = "none"
    for hit in hits:
        kind, _fiscal = classify_hit(hit)
        if kind == "confirmed":
            klass = "confirmed"
        elif klass == "none":
            klass = "possible"
    pep = meta.get("declares_pep") is True or meta.get("partners_pep") is True
    third = meta.get("third_party_payments") is True
    foreign = meta.get("foreign_operations") is True
    vulnerable = match_vulnerable_activity(*activity_texts_for_entity(entity))
    over = _cfdi_over_notice(entity, expedient)
    missing = _controllers_missing(entity)
    material = bool(codes & _MATERIAL)
    soft = bool(codes & _SOFT)
    city = _city_index(entity)

    if material:
        integrity = 3
    elif soft:
        integrity = 2
    else:
        integrity = 0
    if klass == "confirmed":
        screening_r = 4
    elif klass == "possible":
        screening_r = 3
    else:
        screening_r = 0
    if missing:
        controller = 3
    else:
        controller = 0
    activity = 0
    if vulnerable:
        activity = 3 if over else 2
    transactional = 0
    if third:
        transactional += 3
    if foreign:
        transactional += 2
    transactional = min(4, transactional)
    geography = 2
    if city is not None:
        if city < 30:
            geography = 3
        elif city < 50:
            geography = 2
        elif city < 70:
            geography = 1
        else:
            geography = 0
    identity = 3 if "rfc_mismatch" in codes or "legal_name_mismatch" in codes else 0
    representative = (
        2
        if "id_expired_or_unreadable" in codes or "legal_name_mismatch" in codes
        else 0
    )
    authenticity = 0
    conduct = 2 if third or foreign else 0

    ratings = {
        "weight_authenticity": authenticity,
        "weight_identity": identity,
        "weight_controller": controller,
        "weight_representative": representative,
        "weight_activity": activity,
        "weight_geography": geography,
        "weight_transactional": transactional,
        "weight_integrity": integrity,
        "weight_screening": screening_r,
        "weight_conduct": conduct,
    }
    inherent = 0.0
    lines = []
    for slug, rating in ratings.items():
        weight = _pt(table, slug, 0)
        share = round(_share(rating, weight), 2)
        inherent += share
        lines.append(
            {
                "slug": slug,
                "rating": rating,
                "weight": weight,
                "points": share,
            }
        )
    adjustments: list[dict[str, Any]] = []
    extra = 0.0

    def bump(slug: str, on: bool) -> None:
        nonlocal extra
        if not on:
            return
        value = _pt(table, slug, 0)
        extra += value
        adjustments.append({"slug": slug, "points": value})

    bump("adjust_pep", pep)
    bump("adjust_vulnerable", bool(vulnerable))
    bump("adjust_third_party", third)
    bump("adjust_foreign", foreign)
    bump("adjust_controller_missing", missing)
    bump("adjust_mismatch", material)
    total = _clamp(inherent + extra)
    return {
        "total": total,
        "inherent": round(inherent, 1),
        "adjustments_total": round(extra, 1),
        "color": _color(total, table),
        "city_index": city,
        "vulnerable": bool(vulnerable),
        "cfdi_over_notice": over,
        "lines": lines,
        "adjustments": adjustments,
    }
