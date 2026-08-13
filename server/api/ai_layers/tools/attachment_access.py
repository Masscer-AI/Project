"""Shared ACL for MessageAttachment agent tools."""

from __future__ import annotations

from django.db.models import Q


def attachments_visible_q(
    *,
    user_id: int | None,
    conversation_id: str | None,
    organization_id: int | None = None,
) -> Q:
    """
    Attachments the actor may list.

    Authenticated user: their files across conversations they own (web chats
    and WhatsApp threads linked via WSContact.user), plus rows with user_id set.
    Anonymous (widget / unlinked WhatsApp): current conversation only.
    """
    if user_id is not None:
        from api.messaging.conversation_access import user_owned_conversations_q
        from api.messaging.models import Conversation

        owned = Conversation.objects.filter(
            user_owned_conversations_q(int(user_id), organization_id),
        ).exclude(status="deleted")
        return Q(user_id=int(user_id)) | Q(conversation__in=owned)

    if conversation_id:
        return Q(conversation_id=conversation_id)

    raise ValueError("list_attachments requires user_id or conversation_id")


def user_can_access_attachment(
    att,
    *,
    user_id: int | None,
    conversation_id: str | None,
    organization_id: int | None = None,
) -> bool:
    """Whether read/send tools may use this attachment."""
    if conversation_id and str(att.conversation_id) == str(conversation_id):
        return True
    if user_id is None:
        return False
    if att.user_id is not None and int(att.user_id) == int(user_id):
        return True

    from api.messaging.conversation_access import user_owned_conversations_q
    from api.messaging.models import Conversation

    return (
        Conversation.objects.filter(
            user_owned_conversations_q(int(user_id), organization_id),
            pk=att.conversation_id,
        )
        .exclude(status="deleted")
        .exists()
    )
