"""Per-field citations required by the PLD extraction spec."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


def _optional_str(value: Any) -> Any:
    """Models often emit page numbers as ints; schema fields are strings."""
    if value is None or isinstance(value, str):
        return value
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, float):
        return str(value)
    return value


OptionalCoercedStr = Annotated[str | None, BeforeValidator(_optional_str)]


class FieldProvenance(BaseModel):
    """Minimum output row for one spec campo_id."""

    model_config = ConfigDict(extra="ignore", coerce_numbers_to_str=True)

    campo_id: str
    valor_extraido: OptionalCoercedStr = None
    pagina_origen: OptionalCoercedStr = None
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
