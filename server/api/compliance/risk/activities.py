"""Match a declared giro to an LFPIORPI vulnerable activity."""

from __future__ import annotations

import json
import unicodedata
from functools import lru_cache
from pathlib import Path
from typing import Any


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value.casefold())
    return "".join(ch for ch in text if unicodedata.category(ch) != "Mn")


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    path = Path(__file__).resolve().parent / "catalogs" / "vulnerable_activities_2026.json"
    return json.loads(path.read_text(encoding="utf-8"))


def match_vulnerable_activity(*texts: str) -> dict[str, Any] | None:
    blob = _fold(" ".join(part for part in texts if part))
    if not blob.strip():
        return None
    catalog = _catalog()
    uma = float(catalog["uma_daily_mxn"])
    best: tuple[int, dict[str, Any]] | None = None
    for row in catalog["activities"]:
        for word in row.get("keywords") or []:
            folded = _fold(str(word))
            if folded and folded in blob and (best is None or len(folded) > best[0]):
                best = (len(folded), row)
    if best is None:
        return None
    row = best[1]
    notice = row.get("notice_uma")
    return {
        "fraction": row["fraction"],
        "activity": row["activity"],
        "notice_uma": notice,
        "notice_mxn": round(float(notice) * uma, 2) if notice is not None else None,
        "notice_note": row.get("notice_note") or "",
    }


def activity_texts_for_entity(entity) -> list[str]:
    meta = entity.metadata if isinstance(getattr(entity, "metadata", None), dict) else {}
    texts = [str(meta.get("economic_activity") or "")]
    exp = entity.expedients.order_by("created_at").first() if hasattr(entity, "expedients") else None
    if not exp:
        return texts
    for doc in exp.documents.all():
        if getattr(doc, "document_kind", "") != "constancia_fiscal":
            continue
        payload = doc.extracted_payload if isinstance(doc.extracted_payload, dict) else {}
        for item in payload.get("economic_activities") or []:
            if isinstance(item, dict):
                texts.append(str(item.get("name") or ""))
            elif item:
                texts.append(str(item))
    return texts
