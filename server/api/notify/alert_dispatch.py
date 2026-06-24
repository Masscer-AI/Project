"""
Bridge ConversationAlert → UserNotification using NotificationRule conditions.

Call maybe_dispatch_user_notifications(alert) whenever an alert is created or
re-opened to PENDING so both batch analysis and the raise_alert tool share one path.
"""

from __future__ import annotations

import logging
from typing import Iterable
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils.html import escape
from django.utils import timezone

from api.authenticate.models import RoleAssignment, UserProfile
from api.messaging.models import ConversationAlert, ConversationAlertRule
from api.notify.models import NotificationRule, UserNotification
from api.notify.schemas import NotificationConditionList
from api.utils.email_service import EmailService

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


def _delivery_includes_app(delivery_method: str) -> bool:
    return delivery_method in (
        UserNotification.DELIVERY_APP,
        UserNotification.DELIVERY_ALL,
    )


def emit_in_app_notification_created(notification: UserNotification) -> None:
    """Push a new inbox notification to the target user over Socket.IO."""
    if not _delivery_includes_app(notification.delivery_method):
        return
    from api.notify.actions import notify_user
    from api.notify.serializers import UserNotificationSerializer

    payload = UserNotificationSerializer(notification).data
    notify_user(notification.target_user_id, "in_app_notification_created", payload)


def _delivery_includes_email(delivery_method: str) -> bool:
    return delivery_method in (
        UserNotification.DELIVERY_EMAIL,
        UserNotification.DELIVERY_ALL,
    )


def _alerts_dashboard_url() -> str | None:
    """Deep-link to the alerts queue (pending list is the default when no conversation filter)."""
    base = (getattr(settings, "FRONTEND_URL", None) or "").strip().rstrip("/")
    if not base:
        logger.debug(
            "FRONTEND_URL is unset; alert notification email will have no dashboard link"
        )
        return None
    query = urlencode({"view": "alerts"})
    return f"{base}/dashboard/alerts?{query}"


def _send_user_notification_email(
    *,
    user: User,
    message: str,
    alert_title: str,
    alert_rule_name: str,
    organization_name: str,
    alerts_dashboard_url: str | None,
) -> None:
    """
    First-version alert notification email via Resend.
    Caller should only invoke when a new UserNotification row was created.
    """
    to = (user.email or "").strip()
    if not to:
        logger.debug("Skipping alert notification email: user %s has no email", user.pk)
        return
    try:
        service = EmailService()
    except ValueError:
        logger.warning(
            "Skipping alert notification email: email provider not configured "
            "(user_id=%s)",
            user.pk,
        )
        return

    safe_body = escape(message).replace("\n", "<br>\n")
    footer = (
        f"{escape(alert_title)} · {escape(alert_rule_name)} · "
        f"{escape(organization_name)}"
    )
    if alerts_dashboard_url:
        safe_href = escape(alerts_dashboard_url)
        link_section = (
            '<p style="margin-top:18px;">'
            f'<a href="{safe_href}" style="color:#6d28d9;font-weight:600;">'
            "Ver alertas en el panel"
            "</a></p>"
        )
    else:
        link_section = ""
    html = (
        f"<p>{safe_body}</p>"
        f"{link_section}"
        f'<p style="color:#666;font-size:12px;">{footer}</p>'
    )
    subject = f"Masscer: {alert_rule_name}"[:200]
    try:
        service.send_email(to=to, html=html, subject=subject, from_name="Masscer")
    except Exception:
        logger.exception(
            "Alert notification email failed (user_id=%s, to=%s)",
            user.pk,
            to,
        )


def maybe_dispatch_user_notifications(alert: ConversationAlert) -> None:
    """
    For enabled NotificationRules on this alert's ConversationAlertRule, evaluate
    conditions (n_alerts) and create UserNotification rows for resolved targets.

    Idempotent per (alert, notification_rule, target_user) via get_or_create.
    When delivery is email or all, sends one Resend email per new row (not on updates).
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
        org_name = org.name or str(org.id)
        alert_rule_name = alert_rule.name or "Alert rule"
        alert_title = alert.title or "Alert"
        dashboard_url = _alerts_dashboard_url()
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
                if created and _delivery_includes_email(delivery_method):
                    _send_user_notification_email(
                        user=user,
                        message=message,
                        alert_title=alert_title,
                        alert_rule_name=alert_rule_name,
                        organization_name=org_name,
                        alerts_dashboard_url=dashboard_url,
                    )
                if created:
                    emit_in_app_notification_created(obj)
            except Exception:
                logger.exception(
                    "Failed to create UserNotification alert=%s rule=%s user=%s",
                    alert.id,
                    nr.id,
                    user.id,
                )
