"""
In-memory WhatsApp Cloud API message-template allowlist.

Templates are defined in code (not DB). Meta remains authoritative for
approval/quality; this registry only decides which templates the AI may invoke.
Copy fields (body_text / header_text / footer_text / button labels) mirror the
approved Meta template so stored conversation messages can be interpolated.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

_PLACEHOLDER_RE = re.compile(r"\{\{(\d+)\}\}")

def fill_template_placeholders(text: str, values: list[str] | tuple[str, ...]) -> str:
    """Replace Meta-style {{1}}, {{2}} placeholders with positional values."""
    vals = [str(v) for v in values]

    def repl(match: re.Match[str]) -> str:
        idx = int(match.group(1)) - 1
        if 0 <= idx < len(vals):
            return vals[idx]
        return ""

    return _PLACEHOLDER_RE.sub(repl, text or "")

class WhatsAppTemplateButton(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    index: int = Field(ge=0, description="Zero-based button index in the Meta template.")
    sub_type: Literal["url", "quick_reply"] = "url"
    use_source_conversation_id: bool = False
    label: str = ""
    url: str = ""
    description: str = ""

class WhatsAppTemplateDefinition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(description="Stable local template id used by AI tools.")
    meta_name: str = Field(description="Exact Meta template name.")
    language_code: str = Field(description="Meta language code, e.g. 'en'.")
    category: Literal["UTILITY", "MARKETING", "AUTHENTICATION"] = "UTILITY"
    description: str = ""
    header_type: Literal["none", "text", "image"] = "none"
    header_text: str = ""
    body_text: str = ""
    footer_text: str = ""
    body_variable_count: int = Field(ge=0)
    body_variable_descriptions: tuple[str, ...] = ()
    buttons: tuple[WhatsAppTemplateButton, ...] = ()
    enabled: bool = True

    @model_validator(mode="after")
    def validate_copy_and_descriptions(self) -> WhatsAppTemplateDefinition:
        if (
            self.body_variable_descriptions
            and len(self.body_variable_descriptions) != self.body_variable_count
        ):
            raise ValueError(
                "body_variable_descriptions length must match body_variable_count"
            )
        if self.body_text:
            nums = sorted({int(n) for n in _PLACEHOLDER_RE.findall(self.body_text)})
            expected = list(range(1, self.body_variable_count + 1))
            if nums != expected:
                raise ValueError(
                    "body_text placeholders must be {{1}}…{{N}} matching "
                    "body_variable_count"
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
    header_type="text",
    header_text="Task completed",
    body_text=(
        "I have finished completing the requested task: *{{1}}*, here is a summary:\n"
        "\n"
        "{{2}}\n"
        "\n"
        "Let me know what you think!"
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
            label="Visit website",
            url="https://app.charlytoc.dev/chat?conversation=",
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
    header_type="text",
    header_text="Tarea completada",
    body_text=(
        "He terminado de realizar la tarea solicitada: *{{1}}*, aquí tienes un resumen:\n"
        "\n"
        "{{2}}\n"
        "\n"
        "¡Déjame saber tu opinión!"
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
            label="Ver en Masscer",
            url="https://app.charlytoc.dev/chat?conversation=",
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
    header_type="text",
    header_text="Aprobación pendiente",
    body_text=(
        "Hola, necesito tu aprobación para continuar en la tarea *{{1}}*.\n"
        "\n"
        "Resumen de lo que voy a hacer:\n"
        "{{2}}\n"
        "\n"
        "¿Apruebas este flujo?"
    ),
    body_variable_count=2,
    body_variable_descriptions=(
        "Nombre corto de la tarea (completa *{{1}}*).",
        "Resumen de lo que el agente va a hacer si aprueban (completa {{2}}).",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            label="Sí, permiso concedido.",
            description="Sí, permiso concedido.",
        ),
    ),
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
    header_type="text",
    header_text="Pending approval",
    body_text=(
        "Hi, I need your approval to continue with the task *{{1}}*.\n"
        "\n"
        "Here's what I'm going to do:\n"
        "{{2}}\n"
        "\n"
        "Do you approve this flow?"
    ),
    body_variable_count=2,
    body_variable_descriptions=(
        "Short task name (fills *{{1}}*).",
        "Summary of what the agent will do if approved (fills {{2}}).",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            label="Yes, permission granted",
            description="Yes, permission granted",
        ),
    ),
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
    body_text=(
        "*Expreso Fiscal | Integrarem*\n"
        "\n"
        "Actualización semanal: *{{1}}*\n"
        "\n"
        "Le compartimos los temas relevantes de esta edición:\n"
        "\n"
        "{{2}}\n"
        "\n"
        "Consulte el boletín completo y escuche el resumen ejecutivo en los enlaces siguientes."
    ),
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
            label="Ver boletín completo",
            url="https://integrarem.com.mx/expreso-fiscal/",
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
            label="Escuchar resumen",
            url="https://integrarem.com.mx/expreso-fiscal/audio/",
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
    header_text="Expreso Fiscal | Integrarem",
    body_text=(
        "Ya está disponible la edición correspondiente a {{1}}.\n"
        "\n"
        "Incluye información general sobre {{2}}.\n"
        "\n"
        "Puede consultar el material completo en el siguiente enlace.\n"
        "\n"
        "La información es general e informativa y requiere validación conforme a la operación y documentación de cada caso."
    ),
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
            label="Consultar edición",
            url="https://integrarem.com.mx/expreso-fiscal/",
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
    header_text="Integrarem",
    body_text=(
        "Recibimos su solicitud relacionada con las comunicaciones del Expreso Fiscal.\n"
        "\n"
        "Indíquenos la opción que desea gestionar.\n"
        "\n"
        "Sus datos serán tratados conforme al aviso de privacidad de Integrarem."
    ),
    body_variable_count=0,
    body_variable_descriptions=(),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            label="Continuar recibiendo",
            description="Continuar recibiendo",
        ),
        WhatsAppTemplateButton(
            index=1,
            sub_type="quick_reply",
            label="Actualizar preferencias",
            description="Actualizar preferencias",
        ),
        WhatsAppTemplateButton(
            index=2,
            sub_type="quick_reply",
            label="Solicitar baja",
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
    body_text=(
        "Hola {{1}}, el boletín semanal de Integrarem ya está listo.\n"
        "\n"
        "Le enviamos una copia a su correo registrado. Si desea consultarlo por WhatsApp, seleccione una opción:"
    ),
    body_variable_count=1,
    body_variable_descriptions=(
        "Nombre del destinatario (completa {{1}}), ej. 'Maria'.",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            label="Leer por WhatsApp",
            description="Leer por WhatsApp",
        ),
        WhatsAppTemplateButton(
            index=1,
            sub_type="quick_reply",
            label="Solicitar resumen en audio",
            description="Solicitar resumen en audio",
        ),
        WhatsAppTemplateButton(
            index=2,
            sub_type="quick_reply",
            label="No deseo recibir avisos",
            description="No deseo recibir avisos",
        ),
    ),
    enabled=True,
)

EXPRESO_FISCAL_RESUMEN_SEMANAL = WhatsAppTemplateDefinition(
    id="expreso_fiscal_resumen_semanal_es_mx",
    meta_name="expreso_fiscal_resumen_semanal_es_mx",
    language_code="es_MX",
    category="MARKETING",
    description=(
        "Resumen semanal Expreso Fiscal (Integrarem) por WhatsApp. "
        "Sin header ni footer. Cuerpo con 7 variables: destinatario, "
        "periodo, titular, dos puntos a vigilar, dolar FIX y CETES. "
        "Tres botones de respuesta rapida: 'Leer boletin completo', "
        "'Solicitar resumen en audio', 'No deseo recibir avisos'."
    ),
    header_type="none",
    body_text=(
        "*INTEGRAREM | EXPRESO FISCAL*\n"
        "\n"
        "Hola, {{1}}.\n"
        "\n"
        "🗓️ *Resumen fiscal — {{2}}*\n"
        "\n"
        "🔎 *Titular principal:*\n"
        "{{3}}\n"
        "\n"
        "📌 *Otros puntos a vigilar:*\n"
        "• {{4}}\n"
        "• {{5}}\n"
        "\n"
        "📈 *Pulso económico:*\n"
        "Dólar FIX: {{6}}\n"
        "CETES de referencia: {{7}}\n"
        "\n"
        "Consulte las fuentes oficiales y el análisis general de esta edición "
        "en los recursos compartidos por Integrarem.\n"
        "\n"
        "_Información general; su aplicación puede variar según la operación "
        "y documentación de cada caso._"
    ),
    body_variable_count=7,
    body_variable_descriptions=(
        "Nombre del destinatario (completa {{1}}), ej. 'Maria'.",
        "Fecha o periodo de la edicion (completa {{2}}), "
        "ej. '14 de agosto de 2026'.",
        "Titular principal breve (completa {{3}}).",
        "Nota de radar fiscal 1 (completa {{4}}).",
        "Nota de radar fiscal 2 (completa {{5}}).",
        "Tipo de cambio FIX y fecha de corte (completa {{6}}), "
        "ej. '$17.0530 MXN/USD · 14 ago. 2026'.",
        "CETES de referencia y fecha de corte (completa {{7}}), "
        "ej. '28 dias: 6.40% · 91 dias: 6.48%'.",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            label="Leer boletín completo",
            description="Leer boletín completo",
        ),
        WhatsAppTemplateButton(
            index=1,
            sub_type="quick_reply",
            label="Solicitar resumen en audio",
            description="Solicitar resumen en audio",
        ),
        WhatsAppTemplateButton(
            index=2,
            sub_type="quick_reply",
            label="No deseo recibir avisos",
            description="No deseo recibir avisos",
        ),
    ),
    enabled=True,
)

AVISOS_INTEGRAREM_GENERAL = WhatsAppTemplateDefinition(
    id="avisos_integrarem_general_es_mx",
    meta_name="avisos_integrarem_general",
    language_code="es_MX",
    category="MARKETING",
    description=(
        "Avisos editoriales e institucionales generales de Integrarem "
        "(Expreso Fiscal). Marketing. Header de texto fijo; pie fijo; "
        "cuerpo con 4 variables: destinatario, fecha, tema y desarrollo. "
        "Solo informacion general; no incluir RFC completo, datos bancarios, "
        "contrasenas, e.firma, documentos confidenciales ni conclusiones "
        "personalizadas. {{1}} debe ser unicamente el nombre de la persona. "
        "Tres botones de respuesta rapida: 'Compartir este aviso' "
        "(indicar que puede usar la funcion de compartir de WhatsApp; "
        "no promete reenvio automatico), 'Solicitar audio' (generar y "
        "entregar en el mismo hilo un resumen breve en audio de la edicion "
        "vigente, aclarando que es informacion general), 'Dejar de recibir' "
        "(confirmar brevemente la canalizacion de exclusion; no insistir "
        "ni enviar contenido promocional posterior)."
    ),
    header_type="text",
    header_text="AVISOS INTEGRAREM",
    footer_text="Integrarem | Información general y comunicados",
    body_text=(
        "Hola, {{1}}.\n"
        "\n"
        "Le compartimos un aviso de Integrarem.\n"
        "\n"
        "*Fecha:* {{2}}\n"
        "*Tema:* {{3}}\n"
        "\n"
        "{{4}}\n"
        "\n"
        "Esta información es de carácter general. Su aplicación puede variar "
        "según su situación, régimen, operaciones y documentación. Si requiere "
        "orientación sobre su caso, responda a este mensaje para canalizarle "
        "con el equipo de Integrarem."
    ),
    body_variable_count=4,
    body_variable_descriptions=(
        "Nombre de la persona destinataria (completa {{1}}), "
        "ej. 'María González'. Solo el nombre; no datos fiscales.",
        "Fecha de emision del aviso (completa {{2}}), "
        "ej. '26 de agosto de 2026'.",
        "Titulo concreto del tema (completa {{3}}), "
        "ej. 'Actualización fiscal semanal'.",
        "Desarrollo del aviso general (completa {{4}}). Informacion general, "
        "sin datos confidenciales ni conclusiones personalizadas.",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            label="Compartir este aviso",
            description=(
                "Compartir este aviso. Indicar que puede usar la funcion de "
                "compartir de WhatsApp; no promete reenvio automatico."
            ),
        ),
        WhatsAppTemplateButton(
            index=1,
            sub_type="quick_reply",
            label="Solicitar audio",
            description=(
                "Solicitar audio. Generar y entregar en el mismo hilo un "
                "resumen breve en audio de la edicion vigente, con la "
                "aclaracion de que es informacion general."
            ),
        ),
        WhatsAppTemplateButton(
            index=2,
            sub_type="quick_reply",
            label="Dejar de recibir",
            description=(
                "Dejar de recibir. Confirmar brevemente la canalizacion de "
                "exclusion conforme al proceso de Integrarem; no insistir "
                "ni enviar contenido promocional posterior."
            ),
        ),
    ),
    enabled=True,
)

SEGUIMIENTO_INTEGRAREM_ATENCION = WhatsAppTemplateDefinition(
    id="seguimiento_integrarem_atencion_es_mx",
    meta_name="seguimiento_integrarem_atencion",
    language_code="es_MX",
    category="UTILITY",
    description=(
        "Seguimiento operativo de una atencion, solicitud o servicio ya "
        "esperado por el contacto (Integrarem). Utility; no usar para "
        "campanas, boletines ni promociones generales. Header de texto "
        "fijo; pie fijo; cuerpo con 4 variables: destinatario, atencion "
        "esperada, fecha y detalle operativo general. {{1}} debe ser "
        "unicamente el nombre de la persona. No incluir RFC completo, "
        "datos bancarios, contrasenas, e.firma ni documentos confidenciales. "
        "Tres botones de respuesta rapida: 'Solicitar cita' (pedir datos "
        "minimos y opciones de fecha/horario), 'Tengo una duda' (recibir "
        "y clasificar la duda; orientacion general o canalizacion segun "
        "riesgo), 'Dejar de recibir' (confirmar brevemente la canalizacion "
        "de exclusion)."
    ),
    header_type="text",
    header_text="INTEGRAREM | SEGUIMIENTO",
    footer_text="Integrarem | Atención y seguimiento",
    body_text=(
        "Hola, {{1}}.\n"
        "\n"
        "Le contactamos para dar seguimiento a {{2}}.\n"
        "\n"
        "*Fecha:* {{3}}\n"
        "*Detalle:* {{4}}\n"
        "\n"
        "Si requiere actualizar información o coordinar una revisión con el "
        "equipo de Integrarem, responda a este mensaje."
    ),
    body_variable_count=4,
    body_variable_descriptions=(
        "Nombre de la persona destinataria (completa {{1}}), "
        "ej. 'María González'. Solo el nombre; no datos fiscales.",
        "Atencion, solicitud o proceso previamente esperado (completa {{2}}), "
        "ej. 'su solicitud de revisión contable'.",
        "Fecha de la comunicacion o evento (completa {{3}}), "
        "ej. '26 de agosto de 2026'.",
        "Detalle operativo general, sin informacion confidencial "
        "(completa {{4}}).",
    ),
    buttons=(
        WhatsAppTemplateButton(
            index=0,
            sub_type="quick_reply",
            label="Solicitar cita",
            description=(
                "Solicitar cita. Pedir datos minimos y opciones de "
                "fecha/horario para coordinar la atencion."
            ),
        ),
        WhatsAppTemplateButton(
            index=1,
            sub_type="quick_reply",
            label="Tengo una duda",
            description=(
                "Tengo una duda. Recibir y clasificar la duda; ofrecer "
                "orientacion general o canalizacion segun el nivel de riesgo."
            ),
        ),
        WhatsAppTemplateButton(
            index=2,
            sub_type="quick_reply",
            label="Dejar de recibir",
            description=(
                "Dejar de recibir. Confirmar brevemente la canalizacion de "
                "exclusion conforme al proceso de Integrarem."
            ),
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
    EXPRESO_FISCAL_RESUMEN_SEMANAL.id: EXPRESO_FISCAL_RESUMEN_SEMANAL,
    AVISOS_INTEGRAREM_GENERAL.id: AVISOS_INTEGRAREM_GENERAL,
    SEGUIMIENTO_INTEGRAREM_ATENCION.id: SEGUIMIENTO_INTEGRAREM_ATENCION,
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
        "header_text": template.header_text,
        "body_text": template.body_text,
        "footer_text": template.footer_text,
        "body_variable_count": template.body_variable_count,
        "body_variable_descriptions": list(template.body_variable_descriptions),
        "button_variable_count": template.button_variable_count,
        "buttons": [
            {
                "index": b.index,
                "sub_type": b.sub_type,
                "use_source_conversation_id": b.use_source_conversation_id,
                "label": b.label,
                "url": b.url,
                "description": b.description,
            }
            for b in template.buttons
        ],
    }
