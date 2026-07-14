"""Shared validation helpers for agent task dispatch."""

from django.http import JsonResponse

from api.authenticate.services import FeatureFlagService


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
