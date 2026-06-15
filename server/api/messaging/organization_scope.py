"""Shared org-scoped conversation queries (dashboard list + data export)."""

from __future__ import annotations

from datetime import date, datetime, time

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from api.authenticate.models import Organization


def org_member_user_ids(organization_id) -> list[int]:
    """User ids that belong to an organization (owner + profile members)."""
    org = Organization.objects.filter(id=organization_id).only("owner_id").first()
    if not org:
        return []
    owner_ids = {org.owner_id} if org.owner_id else set()
    member_ids = set(
        User.objects.filter(profile__organization_id=organization_id).values_list(
            "id", flat=True
        )
    )
    return list(owner_ids | member_ids)


def organization_conversations_q(organization_id) -> Q:
    """
    Conversations visible in org scope on the dashboard (scope=org).

    Includes app chats owned by org members (often organization_id is null on the row),
    widget threads, and WhatsApp threads linked via organization or ws_number.
    """
    org_user_ids = org_member_user_ids(organization_id)
    if not org_user_ids:
        return Q(pk__in=[])
    org_org_ids = [organization_id]
    return (
        Q(user_id__in=org_user_ids)
        | Q(
            user__isnull=True,
            chat_widget__created_by_id__in=org_user_ids,
        )
        | (
            Q(user__isnull=True, ws_number__isnull=False)
            & (
                Q(organization_id__in=org_org_ids)
                | Q(ws_number__organization_id__in=org_org_ids)
                | Q(ws_number__user_id__in=org_user_ids)
            )
        )
    )


def date_range_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    start = timezone.make_aware(datetime.combine(date_from, time.min))
    end = timezone.make_aware(datetime.combine(date_to, time.max))
    return start, end


def conversation_activity_in_range_q(start: datetime, end: datetime) -> Q:
    """Conversation had create/update/message/delete activity within [start, end]."""
    return (
        Q(created_at__gte=start, created_at__lte=end)
        | Q(updated_at__gte=start, updated_at__lte=end)
        | Q(last_message_at__gte=start, last_message_at__lte=end)
        | Q(deleted_at__gte=start, deleted_at__lte=end)
    )
