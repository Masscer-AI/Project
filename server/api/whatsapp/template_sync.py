"""Upsert WSTemplate rows from the in-code WhatsApp template registry."""

from __future__ import annotations

from api.whatsapp.models import WSTemplate
from api.whatsapp.template_registry import WHATSAPP_TEMPLATES


def _definition_fields(defn) -> dict:
    return {
        "meta_name": defn.meta_name,
        "language_code": defn.language_code,
        "category": defn.category,
        "description": defn.description or "",
        "header_type": defn.header_type,
        "body_variable_count": defn.body_variable_count,
        "body_variable_descriptions": list(defn.body_variable_descriptions),
        "buttons": [
            {
                "index": b.index,
                "sub_type": b.sub_type,
                "use_source_conversation_id": b.use_source_conversation_id,
                "description": b.description or "",
            }
            for b in defn.buttons
        ],
        "enabled": bool(defn.enabled),
    }


def sync_default_whatsapp_templates(
    *, dry_run: bool = False
) -> tuple[list[str], list[str], list[str]]:
    """
    Upsert each registry template by slug.

    Does not create/delete subscriptions. Does not delete orphan DB rows.
    Returns (created, updated, unchanged) slug lists.
    """
    created: list[str] = []
    updated: list[str] = []
    unchanged: list[str] = []

    for slug, defn in WHATSAPP_TEMPLATES.items():
        fields = _definition_fields(defn)
        existing = WSTemplate.objects.filter(slug=slug).first()
        if existing is None:
            created.append(slug)
            if not dry_run:
                WSTemplate.objects.create(slug=slug, **fields)
            continue

        dirty = False
        for key, value in fields.items():
            if getattr(existing, key) != value:
                dirty = True
                break
        if dirty:
            updated.append(slug)
            if not dry_run:
                for key, value in fields.items():
                    setattr(existing, key, value)
                existing.save()
        else:
            unchanged.append(slug)

    return created, updated, unchanged
