"""Celery tasks for payments / subscriptions."""

from __future__ import annotations

from celery import shared_task
from django.db import transaction
from django.utils import timezone as django_tz

from api.authenticate.models import Organization
from api.payments.billing_helpers import forfeit_subscription_credits
from api.payments.models import Subscription


@shared_task(name="api.payments.tasks.expire_subscriptions_past_end_date")
def expire_subscriptions_past_end_date():
    """
    Mark trial/active subscriptions whose end_date has passed as expired and
    forfeit subscription-bucket credits once per organization.
    """
    now = django_tz.now()
    org_ids = (
        Subscription.objects.filter(
            status__in=("trial", "active"),
            end_date__isnull=False,
            end_date__lt=now,
        )
        .values_list("organization_id", flat=True)
        .distinct()
    )
    for org_id in org_ids:
        with transaction.atomic():
            org = Organization.objects.filter(pk=org_id).select_for_update().first()
            if not org:
                continue
            subs_qs = Subscription.objects.select_for_update().filter(
                organization_id=org_id,
                status__in=("trial", "active"),
                end_date__isnull=False,
                end_date__lt=now,
            )
            if not subs_qs.exists():
                continue
            forfeit_subscription_credits(org)
            subs_qs.update(status="expired", end_date=now, updated_at=now)
