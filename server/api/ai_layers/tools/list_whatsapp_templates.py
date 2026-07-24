"""
Tool: list_whatsapp_templates

Returns locally allowlisted WhatsApp Cloud API templates the agent may send.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from api.whatsapp.template_registry import list_enabled_templates, template_summary


class ListWhatsappTemplatesParams(BaseModel):
    pass


class WhatsappTemplateSummary(BaseModel):
    template_id: str
    meta_name: str
    language_code: str
    category: str
    description: str = ""
    body_variable_count: int
    body_variable_descriptions: list[str] = Field(default_factory=list)
    button_variable_count: int = 0
    buttons: list[dict] = Field(default_factory=list)


class ListWhatsappTemplatesResult(BaseModel):
    templates: list[WhatsappTemplateSummary] = Field(default_factory=list)


def _list_whatsapp_templates_impl() -> ListWhatsappTemplatesResult:
    templates = [
        WhatsappTemplateSummary.model_validate(template_summary(t))
        for t in list_enabled_templates()
    ]
    return ListWhatsappTemplatesResult(templates=templates)


def get_tool(**kwargs) -> dict:
    def list_whatsapp_templates() -> ListWhatsappTemplatesResult:
        return _list_whatsapp_templates_impl()

    return {
        "name": "list_whatsapp_templates",
        "description": (
            "List WhatsApp message templates that Masscer allows sending via "
            "send_ws_template_message. Each entry includes template_id, Meta name, "
            "language, and required body/button variable counts and descriptions. "
            "Call this before send_ws_template_message."
        ),
        "parameters": ListWhatsappTemplatesParams,
        "function": list_whatsapp_templates,
    }
