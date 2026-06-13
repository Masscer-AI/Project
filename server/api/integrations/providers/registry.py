"""
Provider registry for integrations.
"""

from __future__ import annotations

from .base import IntegrationProvider
from .google_drive import GoogleDriveProvider

PROVIDER_REGISTRY: dict[str, type[IntegrationProvider]] = {
    GoogleDriveProvider.provider_key: GoogleDriveProvider,
}


def get_provider(provider_key: str, **kwargs) -> IntegrationProvider:
    cls = PROVIDER_REGISTRY.get(provider_key)
    if cls is None:
        raise ValueError(f"Unknown integration provider: {provider_key}")
    return cls(**kwargs)
