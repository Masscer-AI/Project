"""
Canonical list of feature flag names used across the codebase.
Keep in sync with FEATURE_FLAGS.md. Used by sync_feature_flags command and app startup.

Each entry maps a flag name to its metadata:
  - organization_only: if True the flag can only be assigned at the organization level
                       (not to individual users or as role capabilities).
"""

KNOWN_FEATURE_FLAGS = {
    "manage-organization": {"organization_only": False},
    "alert-rules-manager": {"organization_only": False},
    "tags-management": {"organization_only": False},
    "conversations-dashboard": {"organization_only": False},
    "edit-organization-agent": {"organization_only": False},
    "conversation-analysis": {"organization_only": True},
    "chat-widgets-management": {"organization_only": False},
    "train-agents": {"organization_only": False},
    "audio-tools": {"organization_only": False},
    "image-tools": {"organization_only": False},
    "video-tools": {"organization_only": False},
    "web-scraping": {"organization_only": False},
    "add-files-to-chat": {"organization_only": False},
    "transcribe-on-chat": {"organization_only": False},
    "chat-generate-speech": {"organization_only": False},
    "multi-agent-chat": {"organization_only": False},
    "set-agent-ownership": {"organization_only": False},
}
