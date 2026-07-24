"""
In-memory WhatsApp Cloud API message-template allowlist.

Templates are defined in code (not DB). Meta remains authoritative for
approval/quality; this registry only decides which templates the AI may invoke.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WhatsAppTemplateButton(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(ge=0, description="Zero-based button index in the Meta template.")
    sub_type: Literal["url"] = "url"
    # When True, send_ws_template_message fills the dynamic URL suffix from the
    # authenticated source conversation UUID (chat?conversation=<uuid>).
    use_source_conversation_id: bool = False
    description: str = ""


class WhatsAppTemplateDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Stable local template id used by AI tools.")
    meta_name: str = Field(description="Exact Meta template name.")
    language_code: str = Field(description="Meta language code, e.g. 'en'.")
    category: Literal["UTILITY", "MARKETING", "AUTHENTICATION"] = "UTILITY"
    description: str = ""
    body_variable_count: int = Field(ge=0)
    body_variable_descriptions: tuple[str, ...] = ()
    buttons: tuple[WhatsAppTemplateButton, ...] = ()
    enabled: bool = True

    @model_validator(mode="after")
    def validate_descriptions_length(self) -> WhatsAppTemplateDefinition:
        if (
            self.body_variable_descriptions
            and len(self.body_variable_descriptions) != self.body_variable_count
        ):
            raise ValueError(
                "body_variable_descriptions length must match body_variable_count"
            )
        return self

    @property
    def button_variable_count(self) -> int:
        return sum(1 for b in self.buttons if b.sub_type == "url")


TASK_COMPLETED = WhatsAppTemplateDefinition(
    id="task_completed_en",
    meta_name="task_completed",
    language_code="en",
    category="UTILITY",
    description=(
        "Notify a user that a requested task was completed, with a short summary "
        "and a button linking back to the source Masscer conversation."
    ),
    body_variable_count=2,
    body_variable_descriptions=(
        "Short task description (fills *{{1}}*).",
        "Summary of results (fills {{2}}).",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="url",
            use_source_conversation_id=True,
            description=(
                "Dynamic URL suffix for "
                "https://app.charlytoc.dev/chat?conversation={{1}} "
                "(conversation UUID)."
            ),
        ),
    ),
    enabled=True,
)

SOLICITUD_COMPLETADA = WhatsAppTemplateDefinition(
    id="solicitud_completada_es",
    meta_name="solicitud_completada",
    language_code="es",
    category="UTILITY",
    description=(
        "Notifica en español que una tarea solicitada fue completada, incluye "
        "un resumen y un boton que regresa a la conversacion de Masscer."
    ),
    body_variable_count=2,
    body_variable_descriptions=(
        "Descripcion corta de la tarea (completa *{{1}}*).",
        "Resumen del resultado (completa {{2}}).",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="url",
            use_source_conversation_id=True,
            description=(
                "Sufijo dinamico para "
                "https://app.charlytoc.dev/chat?conversation={{1}} "
                "(UUID de la conversacion)."
            ),
        ),
    ),
    enabled=True,
)


WHATSAPP_TEMPLATES: dict[str, WhatsAppTemplateDefinition] = {
    TASK_COMPLETED.id: TASK_COMPLETED,
    SOLICITUD_COMPLETADA.id: SOLICITUD_COMPLETADA,
}


def get_template(template_id: str) -> WhatsAppTemplateDefinition | None:
    tpl = WHATSAPP_TEMPLATES.get(template_id)
    if tpl is None or not tpl.enabled:
        return None
    return tpl


def list_enabled_templates() -> list[WhatsAppTemplateDefinition]:
    return [t for t in WHATSAPP_TEMPLATES.values() if t.enabled]


def template_summary(template: WhatsAppTemplateDefinition) -> dict:
    return {
        "template_id": template.id,
        "meta_name": template.meta_name,
        "language_code": template.language_code,
        "category": template.category,
        "description": template.description,
        "body_variable_count": template.body_variable_count,
        "body_variable_descriptions": list(template.body_variable_descriptions),
        "button_variable_count": template.button_variable_count,
        "buttons": [
            {
                "index": b.index,
                "sub_type": b.sub_type,
                "use_source_conversation_id": b.use_source_conversation_id,
                "description": b.description,
            }
            for b in template.buttons
        ],
    }
