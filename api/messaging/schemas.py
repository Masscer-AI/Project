from pydantic import BaseModel, Field
from typing import Dict, Any, Optional


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
    alerts: list[Alert] = Field(
        default_factory=list,
        description="Lista de alertas que se deben levantar para esta conversación"
    )

