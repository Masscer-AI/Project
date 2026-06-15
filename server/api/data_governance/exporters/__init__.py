from __future__ import annotations

from api.data_governance.exporters.base import BaseExporter
from api.data_governance.exporters.conversations import AgentsExporter, ConversationsExporter
from api.data_governance.exporters.knowledge_base import (
    CompletionsExporter,
    DocumentTemplatesExporter,
    DocumentsExporter,
)

EXPORTERS: dict[str, BaseExporter] = {
    "conversations": ConversationsExporter(),
    "agents": AgentsExporter(),
    "completions": CompletionsExporter(),
    "documents": DocumentsExporter(),
    "document_templates": DocumentTemplatesExporter(),
}

EXPORTER_KEYS = list(EXPORTERS.keys())
