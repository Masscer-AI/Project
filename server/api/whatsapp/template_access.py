"""
Organization-scoped access to WhatsApp templates stored in the DB.

A template with zero subscriptions is public. Otherwise only subscribed orgs
may list/send it. Runtime tools must use these helpers (not the in-code
registry alone).
"""

from __future__ import annotations

from django.db.models import Exists, OuterRef, Q, QuerySet

from api.authenticate.models import Organization
from api.whatsapp.models import WSTemplate, WSTemplateSubscription
from api.whatsapp.template_registry import (
    WhatsAppTemplateButton,
    WhatsAppTemplateDefinition,
)


def templates_for_organization(organization: Organization) -> QuerySet[WSTemplate]:
    """Enabled templates available to ``organization`` (public or subscribed)."""
    has_any_sub = Exists(
        WSTemplateSubscription.objects.filter(template_id=OuterRef("pk"))
    )
    org_sub = Exists(
        WSTemplateSubscription.objects.filter(
            template_id=OuterRef("pk"),
            organization_id=organization.id,
        )
    )
    return (
        WSTemplate.objects.filter(enabled=True)
        .annotate(_has_any_sub=has_any_sub, _org_sub=org_sub)
        .filter(Q(_has_any_sub=False) | Q(_org_sub=True))
        .order_by("slug")
    )


def wstemplate_to_definition(row: WSTemplate) -> WhatsAppTemplateDefinition:
    """Map a DB row back to the pydantic definition used by send/list helpers."""
    buttons = tuple(
        WhatsAppTemplateButton(
            index=int(b.get("index", 0)),
            sub_type=b.get("sub_type") or "url",
            use_source_conversation_id=bool(
                b.get("use_source_conversation_id", False)
            ),
            label=b.get("label") or "",
            url=b.get("url") or "",
            description=b.get("description") or "",
        )
        for b in (row.buttons or [])
        if isinstance(b, dict)
    )
    return WhatsAppTemplateDefinition(
        id=row.slug,
        meta_name=row.meta_name,
        language_code=row.language_code,
        category=row.category,
        description=row.description or "",
        header_type=row.header_type or "none",
        header_text=getattr(row, "header_text", "") or "",
        body_text=getattr(row, "body_text", "") or "",
        footer_text=getattr(row, "footer_text", "") or "",
        body_variable_count=row.body_variable_count,
        body_variable_descriptions=tuple(row.body_variable_descriptions or []),
        buttons=buttons,
        enabled=bool(row.enabled),
    )


def get_template_for_organization(
    slug: str,
    organization: Organization,
) -> WhatsAppTemplateDefinition | None:
    """
    Return the pydantic template if ``slug`` is enabled and available to ``organization``.
    """
    template_id = (slug or "").strip()
    if not template_id:
        return None
    row = templates_for_organization(organization).filter(slug=template_id).first()
    if row is None:
        return None
    return wstemplate_to_definition(row)
