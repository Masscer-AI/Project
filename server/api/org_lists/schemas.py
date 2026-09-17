"""Pydantic schema for OrganizationList.config JSON."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ColumnConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    examples: list[str] = Field(default_factory=list)
    can_be_empty: bool = False

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        text = (v or "").strip()
        if not text:
            raise ValueError("column name must not be empty")
        return text

    @field_validator("examples", mode="before")
    @classmethod
    def cap_examples(cls, v):
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("examples must be a list")
        out = [str(item).strip() for item in v if str(item).strip()]
        return out[:5]


class OrganizationListConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    columns: list[ColumnConfig] = Field(default_factory=list)
    sheet_name: str | None = None


def default_config_dict() -> dict:
    return OrganizationListConfig().model_dump()


def parse_list_config(raw) -> OrganizationListConfig:
    if raw is None or raw == {}:
        return OrganizationListConfig()
    if isinstance(raw, OrganizationListConfig):
        return raw
    return OrganizationListConfig.model_validate(raw)


def validate_list_config_for_storage(raw) -> dict:
    return parse_list_config(raw).model_dump()
