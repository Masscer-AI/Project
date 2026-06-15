from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from api.authenticate.models import Organization
from api.data_governance.schemas import DataExportManifestSchema


@dataclass
class ExportArtifact:
    """A file written under the export temp directory (relative path)."""

    relative_path: str
    description: str = ""


@dataclass
class ExporterResult:
    artifacts: list[ExportArtifact] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class BaseExporter(ABC):
    key: str

    @abstractmethod
    def export(
        self,
        *,
        organization: Organization,
        manifest: DataExportManifestSchema,
        output_dir: Path,
    ) -> ExporterResult:
        ...
