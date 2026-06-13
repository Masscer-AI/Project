"""
Pydantic schemas for per-provider integration metadata.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GoogleDriveMetadata(BaseModel):
    """Metadata stored on Integration.metadata for google_drive."""

    model_config = ConfigDict(extra="forbid")

    account_email: str | None = None
    root_folder_id: str | None = None
    granted_scopes: list[str] = []


PROVIDER_METADATA_SCHEMAS: dict[str, type[BaseModel]] = {
    "google_drive": GoogleDriveMetadata,
}


def validate_provider_metadata(provider: str, metadata: dict | None) -> dict:
    """
    Validate and normalize metadata for a provider.

    Returns a JSON-serializable dict suitable for JSONField storage.
    """
    schema = PROVIDER_METADATA_SCHEMAS.get(provider)
    if schema is None:
        return metadata or {}
    validated = schema.model_validate(metadata or {})
    return validated.model_dump(mode="json")
