from pydantic import BaseModel, Field


class ConversationAnalysis(BaseModel):
    """Schema para el análisis de una conversación usando OpenAI."""
    
    summary: str = Field(
        description="Resumen general y conciso de la conversación"
    )
    main_topics: list[str] = Field(
        description="Lista de los temas principales discutidos en la conversación"
    )
    sentiment: str = Field(
        description="Sentimiento general de la conversación: 'positive', 'negative', o 'neutral'"
    )
    key_insights: list[str] = Field(
        default=[],
        description="Insights clave o puntos importantes extraídos de la conversación"
    )
    action_items: list[str] = Field(
        default=[],
        description="Elementos de acción, tareas o compromisos mencionados en la conversación"
    )

