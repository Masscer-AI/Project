"""Organization Tag ids on conversations, documents, and attachments."""

from __future__ import annotations

from django.db.models import Q

from api.messaging.models import Tag

MAX_ORG_ITEM_TAGS = 3


def normalize_tag_ids(raw) -> list[int]:
    if raw is None:
        return []
    if not isinstance(raw, (list, tuple)):
        raise ValueError("tag_ids must be a list of integers.")
    seen: set[int] = set()
    out: list[int] = []
    for item in raw:
        try:
            tid = int(item)
        except (TypeError, ValueError):
            raise ValueError("tag_ids must be a list of integers.") from None
        if tid < 1 or tid in seen:
            continue
        seen.add(tid)
        out.append(tid)
        if len(out) >= MAX_ORG_ITEM_TAGS:
            break
    return out


def parse_tag_ids_payload(raw) -> list[int] | None:
    """None means the client omitted tag_ids; [] means clear."""
    if raw is None or raw == "":
        return None
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return None
        if text.startswith("["):
            import json

            try:
                raw = json.loads(text)
            except json.JSONDecodeError as exc:
                raise ValueError("tag_ids must be a JSON list of integers.") from exc
        else:
            raw = [part.strip() for part in text.split(",") if part.strip()]
    return normalize_tag_ids(raw)


def tag_ids_match_q(field_name: str, tag_ids: list[int]) -> Q:
    """OR-match any of the given ids (int or string stored in JSON)."""
    q = Q()
    for tid in tag_ids:
        q |= Q(**{f"{field_name}__contains": [tid]}) | Q(
            **{f"{field_name}__contains": [str(tid)]}
        )
    return q


def resolve_enabled_org_tag_ids(
    organization_id,
    tag_ids: list[int],
    *,
    strict: bool = False,
) -> list[int]:
    if not tag_ids:
        return []
    if not organization_id:
        if strict:
            raise ValueError("Organization is required to set tags.")
        return []
    valid = list(
        Tag.objects.filter(
            id__in=tag_ids,
            organization_id=organization_id,
            enabled=True,
        ).values_list("id", flat=True)
    )
    id_set = set(valid)
    ordered = [tid for tid in tag_ids if tid in id_set][:MAX_ORG_ITEM_TAGS]
    if strict and len(ordered) != len(tag_ids):
        raise ValueError("One or more tag_ids are invalid for this organization.")
    return ordered


def apply_tag_ids(
    instance,
    *,
    organization_id,
    tag_ids: list[int] | None,
    field: str = "tag_ids",
    strict: bool = True,
    extra_update_fields: list[str] | None = None,
) -> list[int]:
    normalized = normalize_tag_ids(tag_ids)
    ordered = resolve_enabled_org_tag_ids(
        organization_id,
        normalized,
        strict=strict,
    )
    setattr(instance, field, ordered)
    fields = [field, *(extra_update_fields or [])]
    instance.save(update_fields=fields)
    return ordered
