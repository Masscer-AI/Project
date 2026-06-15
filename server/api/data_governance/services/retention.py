from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone

from api.data_governance.models import DataPurgeLog, OrganizationDataPolicy
from api.messaging.models import Conversation, MessageAttachment
from api.messaging.organization_scope import organization_conversations_q

logger = logging.getLogger(__name__)


def _delete_attachment_file(attachment: MessageAttachment) -> None:
    if attachment.file:
        try:
            attachment.file.delete(save=False)
        except Exception:
            logger.exception("Failed to delete attachment file %s", attachment.id)


def purge_deleted_conversations_for_org(policy: OrganizationDataPolicy) -> int:
    days = policy.deleted_conversation_retention_days
    if not days:
        return 0

    cutoff = timezone.now() - timezone.timedelta(days=days)
    qs = Conversation.objects.filter(
        organization_conversations_q(policy.organization_id),
        status="deleted",
        deleted_at__isnull=False,
        deleted_at__lt=cutoff,
    )
    count = qs.count()
    if count:
        qs.delete()
    return count


def purge_attachments_for_org(policy: OrganizationDataPolicy) -> int:
    days = policy.attachment_retention_days
    if not days:
        return 0

    cutoff = timezone.now() - timezone.timedelta(days=days)
    qs = MessageAttachment.objects.filter(
        conversation__in=Conversation.objects.filter(
            organization_conversations_q(policy.organization_id),
        ),
        kind="file",
        created_at__lt=cutoff,
    )
    count = 0
    for attachment in qs.iterator():
        _delete_attachment_file(attachment)
        attachment.delete()
        count += 1
    return count


def run_retention_purge() -> dict:
    """Purge expired data for all orgs with retention policies set."""
    totals = {"deleted_conversations": 0, "attachments": 0}
    policies = OrganizationDataPolicy.objects.select_related("organization").filter(
        organization__isnull=False,
    )

    for policy in policies:
        with transaction.atomic():
            conv_count = purge_deleted_conversations_for_org(policy)
            att_count = purge_attachments_for_org(policy)

            if conv_count:
                DataPurgeLog.objects.create(
                    organization=policy.organization,
                    category=DataPurgeLog.Category.DELETED_CONVERSATIONS,
                    count=conv_count,
                )
                totals["deleted_conversations"] += conv_count

            if att_count:
                DataPurgeLog.objects.create(
                    organization=policy.organization,
                    category=DataPurgeLog.Category.ATTACHMENTS,
                    count=att_count,
                )
                totals["attachments"] += att_count

    return totals
