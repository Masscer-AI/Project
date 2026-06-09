"""
Catalog of valid onboarding/assignment button actions.

Single source of truth so the platform assistant does NOT invent flows.
- NAVIGATE_TARGETS: keys that resolve to a concrete frontend path.
- FOCUS_TARGETS: keys that resolve to a DOM element marked with
  data-onboarding-target="<key>" (the panel scrolls to + highlights it).

Anything not listed here must NOT be used in a step button.
"""

from __future__ import annotations

NAVIGATE_TARGETS: dict[str, dict] = {
    "chat": {
        "path": "/chat",
        "description": "Open the main chat.",
    },
    "organization_members": {
        "path": "/organization?activeTab=members",
        "description": "Organization members tab (invite / manage members).",
    },
    "organization_roles": {
        "path": "/organization?activeTab=roles",
        "description": "Organization roles tab (create / assign roles).",
    },
    "organization_settings": {
        "path": "/organization?activeTab=settings",
        "description": "Organization settings tab (name, logo, timezone).",
    },
    "organization_billing": {
        "path": "/organization?activeTab=billing",
        "description": "Billing tab (current plan and credit balance). "
        "Note: viewing invoices is NOT available yet.",
    },
    "knowledge_base": {
        "path": "/knowledge-base",
        "description": "Knowledge base (collections, documents, training).",
    },
    "chat_widgets": {
        "path": "/chat-widgets",
        "description": "Embeddable chat widgets manager.",
    },
}

FOCUS_TARGETS: dict[str, dict] = {
    "agents-modal-trigger": {
        "route": "/chat",
        "description": "The 'Agents' button in the chat header that opens the agents modal.",
    },
}


def resolve_navigate_path(target: str | None) -> str | None:
    """Resolve a navigate target key to a path. Accepts raw paths too."""
    if not target:
        return None
    if target in NAVIGATE_TARGETS:
        return NAVIGATE_TARGETS[target]["path"]
    if target.startswith("/"):
        return target
    return None


def resolve_focus_route(target: str | None) -> str | None:
    if not target:
        return None
    entry = FOCUS_TARGETS.get(target)
    return entry["route"] if entry else None


def is_valid_navigate_target(target: str | None) -> bool:
    if not target:
        return False
    return target in NAVIGATE_TARGETS or target.startswith("/")


def is_valid_focus_target(target: str | None) -> bool:
    return bool(target) and target in FOCUS_TARGETS


def onboarding_actions_catalog() -> dict:
    """Catalog payload for read_masscer_instructions."""
    return {
        "navigate_targets": [
            {"key": k, "path": v["path"], "description": v["description"]}
            for k, v in NAVIGATE_TARGETS.items()
        ],
        "focus_targets": [
            {"key": k, "route": v["route"], "description": v["description"]}
            for k, v in FOCUS_TARGETS.items()
        ],
    }
