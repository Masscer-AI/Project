"""Re-export attachment ACL for agent tools."""

from api.messaging.attachment_access import (
    apply_attachment_ownership,
    attachment_belongs_to_payload,
    attachments_visible_q,
    user_can_access_attachment,
    user_can_manage_attachment,
)

__all__ = [
    "apply_attachment_ownership",
    "attachment_belongs_to_payload",
    "attachments_visible_q",
    "user_can_access_attachment",
    "user_can_manage_attachment",
]
