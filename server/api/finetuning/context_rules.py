"""Pydantic schema for Completion.context_rules JSON."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CompletionContextRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    include_always: bool = False
    include_for_tags: list[int] = Field(default_factory=list)

    @field_validator("include_for_tags", mode="before")
    @classmethod
    def coerce_tag_ids(cls, v):
        if v is None:
            return []
        if not isinstance(v, list):
            raise ValueError("include_for_tags must be a list")
        out: list[int] = []
        for item in v:
            if isinstance(item, bool):
                raise ValueError("include_for_tags must contain integers")
            out.append(int(item))
        return out

    def to_json_dict(self) -> dict:
        return self.model_dump()


def default_context_rules_dict() -> dict:
    return CompletionContextRules().to_json_dict()


def parse_context_rules(raw) -> CompletionContextRules:
    if raw is None or raw == {}:
        return CompletionContextRules()
    if isinstance(raw, CompletionContextRules):
        return raw
    return CompletionContextRules.model_validate(raw)


def validate_context_rules_for_storage(raw) -> dict:
    return parse_context_rules(raw).to_json_dict()
