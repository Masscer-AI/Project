from __future__ import annotations

from api.data_governance.exporters.base import BaseExporter
from api.data_governance.exporters.conversations import AgentsExporter, ConversationsExporter

EXPORTERS: dict[str, BaseExporter] = {
    "conversations": ConversationsExporter(),
    "agents": AgentsExporter(),
}

EXPORTER_KEYS = list(EXPORTERS.keys())
