from __future__ import annotations

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

MATCH_LIMIT = 5
MATCH_THRESHOLD = 0.7


def _joined(*parts) -> str:
    return " ".join(str(part).strip() for part in parts if part and str(part).strip())


def _ids(*values) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            out.append(text)
    return out


def _person(role: str, name: str, properties: dict) -> dict | None:
    cleaned = name.strip()
    if not cleaned:
        return None
    props = {"name": [cleaned], **properties}
    return {"role": role, "name": cleaned, "properties": props}


def ppe_targets(entity) -> list[dict]:
    meta = entity.metadata if isinstance(entity.metadata, dict) else {}
    rows: list[dict] = []
    if getattr(entity, "person_type", "") == "persona_moral":
        representative = meta.get("representative") if isinstance(meta.get("representative"), dict) else {}
        surnames = representative.get("surnames") or _joined(
            representative.get("paternal_surname"),
            representative.get("maternal_surname"),
        )
        identification = (
            representative.get("identification")
            if isinstance(representative.get("identification"), dict)
            else {}
        )
        extra = {}
        if representative.get("date_of_birth"):
            extra["birthDate"] = [str(representative["date_of_birth"])]
        numbers = _ids(
            representative.get("curp"),
            representative.get("rfc"),
            identification.get("document_number"),
        )
        if numbers:
            extra["idNumber"] = numbers
        person = _person(
            "representante",
            _joined(representative.get("given_names"), surnames),
            extra,
        )
        if person:
            rows.append(person)
        controllers = meta.get("controllers") if isinstance(meta.get("controllers"), list) else []
        for item in controllers:
            if not isinstance(item, dict):
                continue
            extra = {}
            numbers = _ids(item.get("rfc"))
            if numbers:
                extra["idNumber"] = numbers
            person = _person("beneficiario_controlador", str(item.get("name") or ""), extra)
            if person:
                rows.append(person)
        return rows

    surnames = meta.get("surnames") or _joined(
        meta.get("paternal_surname"),
        meta.get("maternal_surname"),
    )
    identification = meta.get("identification") if isinstance(meta.get("identification"), dict) else {}
    extra = {}
    if meta.get("date_of_birth"):
        extra["birthDate"] = [str(meta["date_of_birth"])]
    if meta.get("nationality"):
        extra["nationality"] = [str(meta["nationality"])]
    if meta.get("country_of_birth"):
        extra["birthCountry"] = [str(meta["country_of_birth"])]
    numbers = _ids(meta.get("curp"), meta.get("rfc"), identification.get("document_number"))
    if numbers:
        extra["idNumber"] = numbers
    person = _person(
        "titular",
        _joined(meta.get("given_names"), surnames) or str(meta.get("name") or ""),
        extra,
    )
    if person:
        rows.append(person)
    if meta.get("is_own_controller") is False:
        controller = meta.get("controller") if isinstance(meta.get("controller"), dict) else {}
        extra = {}
        numbers = _ids(controller.get("rfc"))
        if numbers:
            extra["idNumber"] = numbers
        person = _person(
            "beneficiario_controlador",
            str(controller.get("name") or ""),
            extra,
        )
        if person:
            rows.append(person)
    return rows


def _hit(item: dict) -> dict:
    props = item.get("properties") if isinstance(item.get("properties"), dict) else {}
    topics = props.get("topics") if isinstance(props.get("topics"), list) else []
    return {
        "id": str(item.get("id") or ""),
        "caption": str(item.get("caption") or ""),
        "score": item.get("score"),
        "topics": [str(topic) for topic in topics],
    }


def run_ppe_screening(entity) -> dict:
    targets = ppe_targets(entity)
    if not targets:
        return {"checks": []}
    api_key = getattr(settings, "OPEN_SANCTIONS_API_KEY", "") or ""
    if not api_key:
        raise RuntimeError("OPEN_SANCTIONS_API_KEY is not set")
    queries = {
        f"q{index}": {"schema": "Person", "properties": row["properties"]}
        for index, row in enumerate(targets)
    }
    base = getattr(settings, "OPEN_SANCTIONS_API_URL", "https://api.opensanctions.org")
    response = requests.post(
        f"{base}/match/peps",
        json={"queries": queries},
        headers={"Authorization": f"ApiKey {api_key}"},
        params={"limit": MATCH_LIMIT, "threshold": MATCH_THRESHOLD},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    responses = body.get("responses") if isinstance(body, dict) else {}
    if not isinstance(responses, dict):
        responses = {}
    checks = []
    for index, row in enumerate(targets):
        block = responses.get(f"q{index}") or {}
        if not isinstance(block, dict):
            raise RuntimeError("OpenSanctions match failed")
        status = block.get("status")
        if status not in (None, 200):
            raise RuntimeError("OpenSanctions match failed")
        hits = [
            _hit(item)
            for item in (block.get("results") or [])
            if isinstance(item, dict) and item.get("match")
        ]
        checks.append(
            {
                "role": row["role"],
                "name": row["name"],
                "hit_count": len(hits),
                "hits": hits,
            }
        )
    return {"checks": checks}
