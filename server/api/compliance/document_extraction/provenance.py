"""Per-field citations required by the PLD extraction spec."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class FieldProvenance(BaseModel):
    """Minimum output row for one spec campo_id."""

    model_config = ConfigDict(extra="ignore")

    campo_id: str
    valor_extraido: str | None = None
    pagina_origen: str | None = None
    texto_origen: str | None = None
    confianza_extraccion: float | None = Field(default=None, ge=0, le=1)
    estado_validacion: Literal[
        "extraido",
        "validado",
        "inconsistente",
        "no_encontrado",
        "requiere_revision",
    ] = "extraido"


class ProvenanceMixin(BaseModel):
    provenances: list[FieldProvenance] = Field(default_factory=list)
