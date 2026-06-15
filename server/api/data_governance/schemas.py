from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from api.data_governance.constants import (
    EXPORT_MAX_DATE_RANGE_DAYS,
    MIN_ATTACHMENT_RETENTION_DAYS,
    MIN_DELETED_CONVERSATION_RETENTION_DAYS,
)


class OrganizationDataPolicySchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deleted_conversation_retention_days: Optional[int] = Field(
        default=None,
        ge=MIN_DELETED_CONVERSATION_RETENTION_DAYS,
        description="null = keep forever",
    )
    attachment_retention_days: Optional[int] = Field(
        default=None,
        ge=MIN_ATTACHMENT_RETENTION_DAYS,
        description="null = keep forever",
    )


class ConversationsExportCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    include_attachments: bool = False
    include_deleted: bool = False


class AgentsExportCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False


class CompletionsExportCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False


class DocumentsExportCategory(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = False
    include_files: bool = False


class ExportCategoriesSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversations: ConversationsExportCategory = Field(default_factory=ConversationsExportCategory)
    agents: AgentsExportCategory = Field(default_factory=AgentsExportCategory)
    completions: CompletionsExportCategory = Field(default_factory=CompletionsExportCategory)
    documents: DocumentsExportCategory = Field(default_factory=DocumentsExportCategory)


class DataExportManifestSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date_from: date
    date_to: date
    categories: ExportCategoriesSchema

    @model_validator(mode="after")
    def validate_date_range(self) -> "DataExportManifestSchema":
        if self.date_to < self.date_from:
            raise ValueError("date_to must be on or after date_from")
        span = (self.date_to - self.date_from).days
        if span > EXPORT_MAX_DATE_RANGE_DAYS:
            raise ValueError(
                f"Date range cannot exceed {EXPORT_MAX_DATE_RANGE_DAYS} days"
            )
        if not any(
            [
                self.categories.conversations.enabled,
                self.categories.agents.enabled,
                self.categories.completions.enabled,
                self.categories.documents.enabled,
            ]
        ):
            raise ValueError("At least one export category must be enabled")
        return self


def parse_export_manifest(data: dict) -> DataExportManifestSchema:
    return DataExportManifestSchema.model_validate(data)


def parse_policy_patch(data: dict) -> OrganizationDataPolicySchema:
    return OrganizationDataPolicySchema.model_validate(data)
