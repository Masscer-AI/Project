"""
Bridge ConversationAlert → UserNotification using NotificationRule conditions.

Call maybe_dispatch_user_notifications(alert) whenever an alert is created or
re-opened to PENDING so both batch analysis and the raise_alert tool share one path.
"""

from __future__ import annotations

import logging
from typing import Iterable

from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone

from api.authenticate.models import RoleAssignment, UserProfile
from api.messaging.models import ConversationAlert, ConversationAlertRule
from api.notify.models import NotificationRule, UserNotification
from api.notify.schemas import NotificationConditionList

logger = logging.getLogger(__name__)

# Count alerts for this rule that still need team attention (dashboard-style).
ACTIONABLE_STATUSES = ("PENDING", "NOTIFIED")


def count_actionable_alerts_for_rule(alert_rule: ConversationAlertRule) -> int:
    return ConversationAlert.objects.filter(
        alert_rule=alert_rule,
        status__in=ACTIONABLE_STATUSES,
    ).count()


def _users_with_role_in_org(role_id, organization_id) -> list[User]:
    today = timezone.now().date()
    qs = RoleAssignment.objects.filter(
        organization_id=organization_id,
        role_id=role_id,
        from_date__lte=today,
    ).filter(Q(to_date__isnull=True) | Q(to_date__gte=today))
    return list({ra.user for ra in qs.select_related("user")})


def resolve_notification_targets(rule: NotificationRule) -> list[User]:
    if rule.notify_to_user_id:
        return [rule.notify_to_user]
    if rule.notify_to_role_id:
        return _users_with_role_in_org(rule.notify_to_role_id, rule.organization_id)
    if rule.notify_to_org_id:
        org = rule.notify_to_org
        today = timezone.now().date()
        user_ids: set[int] = set()
        if org.owner_id:
            user_ids.add(org.owner_id)
        user_ids.update(
            UserProfile.objects.filter(
                organization=org,
                is_active=True,
            ).values_list("user_id", flat=True)
        )
        user_ids.update(
            RoleAssignment.objects.filter(
                organization=org,
                from_date__lte=today,
            )
            .filter(Q(to_date__isnull=True) | Q(to_date__gte=today))
            .values_list("user_id", flat=True)
        )
        return list(User.objects.filter(id__in=user_ids))
    return []


def _map_delivery(method: str) -> str:
    allowed = {
        UserNotification.DELIVERY_APP,
        UserNotification.DELIVERY_EMAIL,
        UserNotification.DELIVERY_ALL,
    }
    return method if method in allowed else UserNotification.DELIVERY_APP


def maybe_dispatch_user_notifications(alert: ConversationAlert) -> None:
    """
    For enabled NotificationRules on this alert's ConversationAlertRule, evaluate
    conditions (n_alerts) and create UserNotification rows for resolved targets.

    Idempotent per (alert, notification_rule, target_user) via get_or_create.
    """
    if alert.status not in ACTIONABLE_STATUSES:
        return

    alert_rule = alert.alert_rule
    org = alert_rule.organization
    n_alerts = count_actionable_alerts_for_rule(alert_rule)

    rules = NotificationRule.objects.filter(
        organization=org,
        alert_rule=alert_rule,
        enabled=True,
    ).select_related(
        "notify_to_user",
        "notify_to_role",
        "notify_to_org",
        "organization",
        "alert_rule",
    )

    for nr in rules:
        try:
            cond_list = NotificationConditionList(conditions=nr.conditions)
        except Exception as exc:
            logger.warning(
                "Skipping notification rule %s: invalid conditions: %s",
                nr.id,
                exc,
            )
            continue

        matched = None
        for cond in cond_list.conditions:
            if cond.is_met(n_alerts):
                matched = cond
                break

        if not matched:
            continue

        message = matched.render_message(n_alerts)
        delivery_method = _map_delivery(matched.delivery_method)
        targets: Iterable[User] = resolve_notification_targets(nr)
        if not targets:
            logger.debug(
                "Notification rule %s: no targets resolved for alert %s",
                nr.id,
                alert.id,
            )
            continue

        now = timezone.now()
        for user in targets:
            try:
                obj, created = UserNotification.objects.get_or_create(
                    alert=alert,
                    notification_rule=nr,
                    target_user=user,
                    defaults={
                        "organization": org,
                        "delivery_method": delivery_method,
                        "message": message,
                        "delivered_at": now,
                    },
                )
                if not created and obj.message != message:
                    obj.message = message
                    obj.delivery_method = delivery_method
                    obj.delivered_at = now
                    obj.save(
                        update_fields=["message", "delivery_method", "delivered_at"]
                    )
            except Exception:
                logger.exception(
                    "Failed to create UserNotification alert=%s rule=%s user=%s",
                    alert.id,
                    nr.id,
                    user.id,
                )
