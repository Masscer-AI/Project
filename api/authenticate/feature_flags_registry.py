"""
Canonical list of feature flag names used across the codebase.
Keep in sync with FEATURE_FLAGS.md. Used by sync_feature_flags command and app startup.
"""

KNOWN_FEATURE_FLAGS = (
    "manage-organization",
    "alert-rules-manager",
    "tags-management",
    "conversations-dashboard",
    "organization-agents-admin",
    "conversation-analysis",
)
