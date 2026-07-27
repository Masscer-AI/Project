"""Shared validation helpers for agent task dispatch."""

from django.core.cache import cache
from django.http import JsonResponse

from api.authenticate.services import FeatureFlagService

AGENT_TASK_ACTIVE_CACHE_TIMEOUT = 3600


def agent_task_active_cache_key(conversation_id: str) -> str:
    return f"agent_task_active_{conversation_id}"


def mark_agent_task_active(conversation_id: str) -> None:
    """Mark a conversation as having an in-flight agent task (covers enqueue→session gap)."""
    cache.set(
        agent_task_active_cache_key(str(conversation_id)),
        True,
        timeout=AGENT_TASK_ACTIVE_CACHE_TIMEOUT,
    )


def clear_agent_task_active(conversation_id: str) -> None:
    cache.delete(agent_task_active_cache_key(str(conversation_id)))


def is_agent_task_marked_active(conversation_id: str) -> bool:
    return bool(cache.get(agent_task_active_cache_key(str(conversation_id))))


def conversation_has_active_agent_session(conversation) -> bool:
    from api.ai_layers.models import AgentSession

    return AgentSession.objects.filter(
        conversation=conversation,
        ended_at__isnull=True,
        dismissed_at__isnull=True,
    ).exists()


def is_agent_task_active_for_conversation(conversation) -> bool:
    """
    Server truth for stop-button reconciliation.

    True while a Celery run is pending/running: either the dispatch cache flag
    is set, or an AgentSession is still open. Multi-agent gaps keep the cache
    flag until the final finish (no next_agent_slug).
    """
    conversation_id = str(conversation.id)
    if is_agent_task_marked_active(conversation_id):
        return True
    return conversation_has_active_agent_session(conversation)


def validate_conversation_access(conversation, user, user_org):
    is_owner = conversation.user_id == user.id
    is_org_member = (
        user_org is not None
        and conversation.organization_id is not None
        and conversation.organization_id == user_org.id
    )
    if not is_owner and not is_org_member:
        return JsonResponse(
            {"error": "You don't have access to this conversation"},
            status=403,
        )
    return None


def parse_client_datetime(client_datetime):
    if client_datetime is not None and not isinstance(client_datetime, dict):
        return None, JsonResponse(
            {"error": "client_datetime must be an object when provided"},
            status=400,
        )
    return client_datetime, None


def parse_regenerate_message_id(regenerate_message_id, *, conversation, user):
    if regenerate_message_id is None:
        return None, None
    try:
        regenerate_message_id = int(regenerate_message_id)
    except (TypeError, ValueError):
        return None, JsonResponse(
            {"error": "regenerate_message_id must be an integer"},
            status=400,
        )
    can_edit_data, _ = FeatureFlagService.is_feature_enabled(
        "can-edit-conversation-data",
        organization=conversation.organization,
        user=user,
    )
    if not can_edit_data:
        return None, JsonResponse(
            {
                "error": (
                    "Regenerating from a user message removes later history. "
                    "The 'can-edit-conversation-data' feature is not enabled for you."
                ),
            },
            status=403,
        )
    return regenerate_message_id, None
