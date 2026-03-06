from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, Literal


class Alert(BaseModel):
    """Schema para una alerta levantada por la IA."""
    
    id: str = Field(
        description="ID (UUID) de la alert rule que se levanta"
    )
    extractions: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Datos extraídos de la conversación según los requerimientos de la alert rule"
    )


class ConversationAnalysisResult(BaseModel):
    """Schema para el resultado del análisis de una conversación con detección de alertas."""
    
    reasoning: str = Field(
        description="Explicación de por qué la conversación levanta o no una o varias alertas"
    )
    summary: str = Field(
        description="Resumen de la conversación en el mismo idioma en que se desarrolló la conversación"
    )
    suggested_tags: Optional[list[int]] = Field(
        default=None,
        description="Lista de IDs de tags sugeridas para esta conversación (solo tags habilitadas de la organización)"
    )
    alerts: list[Alert] = Field(
        default_factory=list,
        description="Lista de alertas que se deben levantar para esta conversación"
    )


class ChatWidgetStyle(BaseModel):
    primary_color: Optional[str] = Field(
        default=None,
        pattern=r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$",
        description="Primary color in hex format (#RGB or #RRGGBB)",
    )
    theme: Optional[Literal["default", "light", "dark"]] = Field(
        default=None,
        description="Widget theme mode",
    )

