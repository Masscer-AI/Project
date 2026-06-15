from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

from api.authenticate.models import Organization
from api.data_governance.exporters.base import BaseExporter, ExportArtifact, ExporterResult
from api.data_governance.schemas import DataExportManifestSchema
from api.document_templates.models import DocumentTemplate
from api.finetuning.models import Completion
from api.messaging.organization_scope import (
    date_range_bounds,
    model_created_in_range_q,
    model_created_or_updated_in_range_q,
    organization_completions_q,
    organization_documents_q,
)
from api.rag.models import Document

logger = logging.getLogger(__name__)


def _write_json(output_dir: Path, relative_path: str, payload: dict) -> ExportArtifact:
    path = output_dir / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return ExportArtifact(relative_path=relative_path)


def _copy_storage_file(file_field, dest: Path) -> bool:
    if not file_field:
        return False
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with file_field.open("rb") as src, dest.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        return True
    except Exception:
        logger.exception("Failed to copy file to %s", dest)
        return False


class CompletionsExporter(BaseExporter):
    key = "completions"

    def export(
        self,
        *,
        organization: Organization,
        manifest: DataExportManifestSchema,
        output_dir: Path,
    ) -> ExporterResult:
        opts = manifest.categories.completions
        if not opts.enabled:
            return ExporterResult()

        start, end = date_range_bounds(manifest.date_from, manifest.date_to)
        qs = (
            Completion.objects.filter(organization_completions_q(organization.id))
            .filter(model_created_or_updated_in_range_q(start, end))
            .prefetch_related("assignments__agent")
            .distinct()
            .order_by("created_at")
        )

        artifacts: list[ExportArtifact] = []
        exported_count = 0

        for completion in qs:
            agent_ids = list(
                completion.assignments.values_list("agent_id", flat=True)
            )
            payload = {
                "id": completion.id,
                "prompt": completion.prompt,
                "answer": completion.answer,
                "context_rules": completion.context_rules,
                "approved": completion.approved,
                "approved_by_id": completion.approved_by_id,
                "training_generator_id": completion.training_generator_id,
                "agent_ids": agent_ids,
                "created_at": completion.created_at.isoformat()
                if completion.created_at
                else None,
                "updated_at": completion.updated_at.isoformat()
                if completion.updated_at
                else None,
            }
            rel = f"completions/{completion.id}.json"
            artifacts.append(_write_json(output_dir, rel, payload))
            exported_count += 1

        return ExporterResult(
            artifacts=artifacts,
            summary={"completions_exported": exported_count},
        )


class DocumentsExporter(BaseExporter):
    key = "documents"

    def export(
        self,
        *,
        organization: Organization,
        manifest: DataExportManifestSchema,
        output_dir: Path,
    ) -> ExporterResult:
        opts = manifest.categories.documents
        if not opts.enabled:
            return ExporterResult()

        start, end = date_range_bounds(manifest.date_from, manifest.date_to)
        qs = (
            Document.objects.filter(organization_documents_q(organization.id))
            .filter(model_created_in_range_q(start, end))
            .select_related("collection", "collection__agent", "collection__user")
            .prefetch_related("chunk_set")
            .order_by("created_at")
        )

        artifacts: list[ExportArtifact] = []
        exported_count = 0
        files_exported = 0

        for doc in qs:
            chunks = [
                {
                    "id": chunk.id,
                    "content": chunk.content,
                    "brief": chunk.brief,
                    "tags": chunk.tags,
                    "created_at": chunk.created_at.isoformat()
                    if chunk.created_at
                    else None,
                }
                for chunk in doc.chunk_set.all().order_by("id")
            ]
            collection = doc.collection
            payload = {
                "id": doc.id,
                "name": doc.name,
                "text": doc.text,
                "brief": doc.brief,
                "total_tokens": doc.total_tokens,
                "content_type": doc.content_type,
                "drive_file_id": doc.drive_file_id,
                "drive_modified_time": doc.drive_modified_time,
                "created_at": doc.created_at.isoformat() if doc.created_at else None,
                "collection": {
                    "id": collection.id,
                    "name": collection.name,
                    "slug": collection.slug,
                    "agent_id": collection.agent_id,
                    "user_id": collection.user_id,
                },
                "chunks": chunks,
            }
            rel = f"documents/{doc.id}.json"
            artifacts.append(_write_json(output_dir, rel, payload))
            exported_count += 1

            if opts.include_files and doc.file:
                ext = Path(doc.file.name).suffix or ".bin"
                file_rel = f"documents/files/{doc.id}{ext}"
                if _copy_storage_file(doc.file, output_dir / file_rel):
                    artifacts.append(
                        ExportArtifact(
                            relative_path=file_rel,
                            description=f"source file for document {doc.id}",
                        )
                    )
                    files_exported += 1

        return ExporterResult(
            artifacts=artifacts,
            summary={
                "documents_exported": exported_count,
                "document_files_exported": files_exported,
            },
        )


class DocumentTemplatesExporter(BaseExporter):
    key = "document_templates"

    def export(
        self,
        *,
        organization: Organization,
        manifest: DataExportManifestSchema,
        output_dir: Path,
    ) -> ExporterResult:
        opts = manifest.categories.document_templates
        if not opts.enabled:
            return ExporterResult()

        start, end = date_range_bounds(manifest.date_from, manifest.date_to)
        qs = (
            DocumentTemplate.objects.filter(organization=organization)
            .filter(model_created_or_updated_in_range_q(start, end))
            .prefetch_related("agent_assignments__agent")
            .order_by("created_at")
        )

        artifacts: list[ExportArtifact] = []
        exported_count = 0
        files_exported = 0

        for template in qs:
            agent_assignments = [
                {
                    "id": str(assignment.id),
                    "agent_id": assignment.agent_id,
                    "usage_instructions": assignment.usage_instructions,
                    "is_enabled": assignment.is_enabled,
                    "created_at": assignment.created_at.isoformat()
                    if assignment.created_at
                    else None,
                }
                for assignment in template.agent_assignments.all()
            ]
            payload = {
                "id": str(template.id),
                "name": template.name,
                "description": template.description,
                "original_filename": template.original_filename,
                "file_size": template.file_size,
                "content_type": template.content_type,
                "metadata": template.metadata,
                "is_active": template.is_active,
                "created_by_id": template.created_by_id,
                "agent_assignments": agent_assignments,
                "created_at": template.created_at.isoformat()
                if template.created_at
                else None,
                "updated_at": template.updated_at.isoformat()
                if template.updated_at
                else None,
            }
            rel = f"document_templates/{template.id}.json"
            artifacts.append(_write_json(output_dir, rel, payload))
            exported_count += 1

            if template.file:
                ext = Path(template.original_filename or template.file.name).suffix or ".docx"
                file_rel = f"document_templates/files/{template.id}{ext}"
                if _copy_storage_file(template.file, output_dir / file_rel):
                    artifacts.append(
                        ExportArtifact(
                            relative_path=file_rel,
                            description=f"template file for {template.id}",
                        )
                    )
                    files_exported += 1

        return ExporterResult(
            artifacts=artifacts,
            summary={
                "document_templates_exported": exported_count,
                "document_template_files_exported": files_exported,
            },
        )
