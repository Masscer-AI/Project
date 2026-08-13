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
    # url: dynamic Visit website CTA (needs a suffix at send time, unless
    # use_source_conversation_id). quick_reply: static; no send-time parameter.
    sub_type: Literal["url", "quick_reply"] = "url"
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
    # none/text: no header component at send time. image: requires header media.
    header_type: Literal["none", "text", "image"] = "none"
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
        """Dynamic URL buttons that need a send-time text parameter."""
        return sum(1 for b in self.buttons if b.sub_type == "url")

    @property
    def requires_header_image(self) -> bool:
        return self.header_type == "image"


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

APROBACION_PENDIENTE = WhatsAppTemplateDefinition(
    id="aprobacion_pendiente_es",
    meta_name="aprobacion_pendiente",
    language_code="es",
    category="UTILITY",
    description=(
        "Pide aprobacion humana en espanol para continuar un flujo. "
        "Incluye un boton de respuesta rapida 'Si, permiso concedido.'; "
        "el usuario puede rechazar respondiendo en texto libre."
    ),
    body_variable_count=2,
    body_variable_descriptions=(
        "Nombre corto de la tarea (completa *{{1}}*).",
        "Resumen de lo que el agente va a hacer si aprueban (completa {{2}}).",
    ),
    buttons=(),
    enabled=True,
)

APPROVAL_PENDING = WhatsAppTemplateDefinition(
    id="approval_pending_en",
    meta_name="approval_pending",
    language_code="en",
    category="UTILITY",
    description=(
        "Ask for human approval in English before continuing a flow. "
        "Includes a quick-reply button 'Yes, permission granted'; "
        "the user can reject by replying with free-form text."
    ),
    body_variable_count=2,
    body_variable_descriptions=(
        "Short task name (fills *{{1}}*).",
        "Summary of what the agent will do if approved (fills {{2}}).",
    ),
    buttons=(),
    enabled=True,
)

EXPRESO_FISCAL_SEMANAL = WhatsAppTemplateDefinition(
    id="expreso_fiscal_semanal_es_mx",
    meta_name="expreso_fiscal_semanal",
    language_code="es_MX",
    category="MARKETING",
    description=(
        "Boletin semanal Expreso Fiscal (Integrarem). Header con imagen; "
        "cuerpo con fecha/edicion y temas; dos botones de URL dinamicos "
        "(boletin completo y resumen en audio). "
        "Al enviar, provee header_image_attachment_id (UUID de un "
        "MessageAttachment de imagen en la conversacion actual)."
    ),
    header_type="image",
    body_variable_count=2,
    body_variable_descriptions=(
        "Fecha o etiqueta de la edicion (completa *{{1}}*), "
        "ej. 'Al cierre del 8 de agosto de 2026'.",
        "Temas relevantes de la edicion (completa {{2}}).",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="url",
            use_source_conversation_id=False,
            description=(
                "Sufijo dinamico para "
                "https://integrarem.com.mx/expreso-fiscal/{{1}} "
                "(ej. '2026-08-08'). Boton: Ver boletin completo."
            ),
        ),
        WhatsAppTemplateButton(
            index=1,
            sub_type="url",
            use_source_conversation_id=False,
            description=(
                "Sufijo dinamico para "
                "https://integrarem.com.mx/expreso-fiscal/audio/{{1}} "
                "(ej. '2026-08-08'). Boton: Escuchar resumen."
            ),
        ),
    ),
    enabled=True,
)

EXPRESO_FISCAL_RECORDATORIO = WhatsAppTemplateDefinition(
    id="expreso_fiscal_recordatorio_es_mx",
    meta_name="expreso_fiscal_recordatorio",
    language_code="es_MX",
    category="MARKETING",
    description=(
        "Recordatorio de edicion disponible del Expreso Fiscal (Integrarem). "
        "Header de texto fijo; cuerpo con edicion y temas; un boton URL "
        "dinamico 'Consultar edicion'."
    ),
    header_type="text",
    body_variable_count=2,
    body_variable_descriptions=(
        "Edicion / periodo (completa {{1}}), "
        "ej. 'Al cierre del 8 de agosto de 2026'.",
        "Temas generales incluidos (completa {{2}}).",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="url",
            use_source_conversation_id=False,
            description=(
                "Sufijo dinamico para "
                "https://integrarem.com.mx/expreso-fiscal/{{1}} "
                "(ej. '2026-08-08'). Boton: Consultar edicion."
            ),
        ),
    ),
    enabled=True,
)

EXPRESO_FISCAL_PREFERENCIAS = WhatsAppTemplateDefinition(
    id="expreso_fiscal_preferencias_es_mx",
    meta_name="expreso_fiscal_preferencias",
    language_code="es_MX",
    category="UTILITY",
    description=(
        "Gestion de preferencias de comunicaciones del Expreso Fiscal "
        "(Integrarem). Sin variables. Tres botones de respuesta rapida: "
        "'Continuar recibiendo', 'Actualizar preferencias', 'Solicitar baja'."
    ),
    header_type="text",
    body_variable_count=0,
    body_variable_descriptions=(),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            description="Continuar recibiendo",
        ),
        WhatsAppTemplateButton(
            index=1,
            sub_type="quick_reply",
            description="Actualizar preferencias",
        ),
        WhatsAppTemplateButton(
            index=2,
            sub_type="quick_reply",
            description="Solicitar baja",
        ),
    ),
    enabled=True,
)

EXPRESO_FISCAL_BOLETIN_SEMANAL = WhatsAppTemplateDefinition(
    id="expreso_fiscal_boletin_semanal_es_mx",
    meta_name="expreso_fiscal_boletin_semanal",
    language_code="es_MX",
    category="MARKETING",
    description=(
        "Aviso de boletin semanal Integrarem (Expreso Fiscal). Sin header; "
        "cuerpo con nombre del destinatario ({{1}}). "
        "Tres botones de respuesta rapida: 'Leer por WhatsApp', "
        "'Solicitar resumen en audio', 'No deseo recibir avisos'."
    ),
    header_type="none",
    body_variable_count=1,
    body_variable_descriptions=(
        "Nombre del destinatario (completa {{1}}), ej. 'Maria'.",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            description="Leer por WhatsApp",
        ),
        WhatsAppTemplateButton(
            index=1,
            sub_type="quick_reply",
            description="Solicitar resumen en audio",
        ),
        WhatsAppTemplateButton(
            index=2,
            sub_type="quick_reply",
            description="No deseo recibir avisos",
        ),
    ),
    enabled=True,
)


WHATSAPP_TEMPLATES: dict[str, WhatsAppTemplateDefinition] = {
    TASK_COMPLETED.id: TASK_COMPLETED,
    SOLICITUD_COMPLETADA.id: SOLICITUD_COMPLETADA,
    APROBACION_PENDIENTE.id: APROBACION_PENDIENTE,
    APPROVAL_PENDING.id: APPROVAL_PENDING,
    EXPRESO_FISCAL_SEMANAL.id: EXPRESO_FISCAL_SEMANAL,
    EXPRESO_FISCAL_RECORDATORIO.id: EXPRESO_FISCAL_RECORDATORIO,
    EXPRESO_FISCAL_PREFERENCIAS.id: EXPRESO_FISCAL_PREFERENCIAS,
    EXPRESO_FISCAL_BOLETIN_SEMANAL.id: EXPRESO_FISCAL_BOLETIN_SEMANAL,
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
        "header_type": template.header_type,
        "requires_header_image": template.requires_header_image,
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
