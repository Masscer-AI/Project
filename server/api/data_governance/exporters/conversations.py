from __future__ import annotations

import json
import shutil
from pathlib import Path

from api.authenticate.models import Organization
from api.data_governance.exporters.base import BaseExporter, ExportArtifact, ExporterResult
from api.data_governance.schemas import DataExportManifestSchema
from api.messaging.models import Conversation, MessageAttachment
from api.messaging.organization_scope import (
    conversation_activity_in_range_q,
    date_range_bounds,
    organization_conversations_q,
)


class ConversationsExporter(BaseExporter):
    key = "conversations"

    def export(
        self,
        *,
        organization: Organization,
        manifest: DataExportManifestSchema,
        output_dir: Path,
    ) -> ExporterResult:
        opts = manifest.categories.conversations
        if not opts.enabled:
            return ExporterResult()

        start, end = date_range_bounds(manifest.date_from, manifest.date_to)
        qs = Conversation.objects.filter(
            organization_conversations_q(organization.id),
            conversation_activity_in_range_q(start, end),
        )
        if not opts.include_deleted:
            qs = qs.exclude(status="deleted")

        out_dir = output_dir / "conversations"
        out_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[ExportArtifact] = []
        exported_count = 0

        for conv in qs.prefetch_related("messages").order_by("created_at"):
            messages = []
            for msg in conv.messages.order_by("created_at"):
                messages.append(
                    {
                        "id": msg.id,
                        "type": msg.type,
                        "text": msg.text,
                        "metadata": msg.metadata,
                        "attachments": msg.attachments,
                        "rag_sources": msg.rag_sources,
                        "browse_sources": msg.browse_sources,
                        "agents": msg.agents,
                        "created_at": msg.created_at.isoformat() if msg.created_at else None,
                        "updated_at": msg.updated_at.isoformat() if msg.updated_at else None,
                    }
                )

            payload = {
                "id": str(conv.id),
                "title": conv.title,
                "status": conv.status,
                "summary": conv.summary,
                "tags": conv.tags,
                "metadata": conv.metadata,
                "whatsapp_user_number": conv.whatsapp_user_number,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "updated_at": conv.updated_at.isoformat() if conv.updated_at else None,
                "deleted_at": conv.deleted_at.isoformat() if conv.deleted_at else None,
                "messages": messages,
            }
            rel = f"conversations/{conv.id}.json"
            (output_dir / rel).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            artifacts.append(ExportArtifact(relative_path=rel))
            exported_count += 1

            if opts.include_attachments:
                att_qs = MessageAttachment.objects.filter(
                    conversation=conv,
                    kind="file",
                ).exclude(file="")
                for att in att_qs:
                    if not att.file:
                        continue
                    ext = Path(att.file.name).suffix or ".bin"
                    att_rel = f"attachments/{att.id}{ext}"
                    dest = output_dir / att_rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        with att.file.open("rb") as src, dest.open("wb") as dst:
                            shutil.copyfileobj(src, dst)
                        artifacts.append(
                            ExportArtifact(
                                relative_path=att_rel,
                                description=f"attachment for conversation {conv.id}",
                            )
                        )
                    except Exception:
                        continue

        return ExporterResult(
            artifacts=artifacts,
            summary={"conversations_exported": exported_count},
        )


class AgentsExporter(BaseExporter):
    key = "agents"

    def export(
        self,
        *,
        organization: Organization,
        manifest: DataExportManifestSchema,
        output_dir: Path,
    ) -> ExporterResult:
        opts = manifest.categories.agents
        if not opts.enabled:
            return ExporterResult()

        from api.ai_layers.models import Agent

        qs = Agent.objects.filter(organization=organization)

        out_dir = output_dir / "agents"
        out_dir.mkdir(parents=True, exist_ok=True)
        artifacts: list[ExportArtifact] = []
        exported_count = 0

        for agent in qs.order_by("name"):
            payload = {
                "id": agent.id,
                "name": agent.name,
                "slug": agent.slug,
                "model_slug": agent.model_slug,
                "model_provider": agent.model_provider,
                "system_prompt": agent.system_prompt,
                "salute": agent.salute,
                "act_as": agent.act_as,
                "agent_kind": agent.agent_kind,
                "is_public": agent.is_public,
                "default": agent.default,
                "max_tokens": agent.max_tokens,
                "conversation_title_prompt": agent.conversation_title_prompt,
            }
            rel = f"agents/{agent.slug or agent.id}.json"
            (output_dir / rel).write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            artifacts.append(ExportArtifact(relative_path=rel))
            exported_count += 1

        return ExporterResult(
            artifacts=artifacts,
            summary={"agents_exported": exported_count},
        )
