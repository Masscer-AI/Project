"""
Tool: list_whatsapp_templates

Returns WhatsApp Cloud API templates available to the current organization
(public templates or ones with an active WSTemplateSubscription).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.authenticate.models import Organization
from api.whatsapp.template_access import (
    templates_for_organization,
    wstemplate_to_definition,
)
from api.whatsapp.template_registry import template_summary


class ListWhatsappTemplatesParams(BaseModel):
    pass


class WhatsappTemplateSummary(BaseModel):
    template_id: str
    meta_name: str
    language_code: str
    category: str
    description: str = ""
    header_type: str = "none"
    requires_header_image: bool = False
    body_variable_count: int
    body_variable_descriptions: list[str] = Field(default_factory=list)
    button_variable_count: int = 0
    buttons: list[dict] = Field(default_factory=list)


class ListWhatsappTemplatesResult(BaseModel):
    templates: list[WhatsappTemplateSummary] = Field(default_factory=list)


def _list_whatsapp_templates_impl(
    *,
    organization_id,
) -> ListWhatsappTemplatesResult:
    organization = Organization.objects.filter(pk=organization_id).first()
    if not organization:
        raise ValueError("Organization not found")

    templates = [
        WhatsappTemplateSummary.model_validate(
            template_summary(wstemplate_to_definition(row))
        )
        for row in templates_for_organization(organization)
    ]
    return ListWhatsappTemplatesResult(templates=templates)


def get_tool(
    organization_id=None,
    **kwargs,
) -> dict:
    if organization_id is None:
        raise ValueError(
            "list_whatsapp_templates requires organization_id in tool context"
        )

    def list_whatsapp_templates() -> ListWhatsappTemplatesResult:
        return _list_whatsapp_templates_impl(organization_id=organization_id)

    return {
        "name": "list_whatsapp_templates",
        "description": (
            "List WhatsApp message templates that Masscer allows this organization "
            "to send via send_ws_template_message. Each entry includes template_id, "
            "Meta name, language, header_type (image headers need "
            "header_image_attachment_id = MessageAttachment UUID from this "
            "conversation), and required body/button variable counts and "
            "descriptions. Call this before send_ws_template_message."
        ),
        "parameters": ListWhatsappTemplatesParams,
        "function": list_whatsapp_templates,
    }
