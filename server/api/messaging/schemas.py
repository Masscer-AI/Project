from pydantic import BaseModel, ConfigDict, Field, field_validator
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


class ChatWidgetCapability(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        description="Internal tool name, e.g. read_attachment",
    )
    type: Literal["internal_tool"] = Field(
        default="internal_tool",
        description="Capability type",
    )
    enabled: bool = Field(
        default=True,
        description="Whether this capability is enabled",
    )

    @field_validator("name")
    @classmethod
    def validate_name_not_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Capability name cannot be blank")
        return cleaned


class ChatWidgetCapabilitiesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capabilities: list[ChatWidgetCapability] = Field(default_factory=list)

    @field_validator("capabilities")
    @classmethod
    def validate_unique_capability_names(cls, value: list[ChatWidgetCapability]):
        names = [cap.name for cap in value]
        if len(names) != len(set(names)):
            raise ValueError("Capability names must be unique")
        return value

