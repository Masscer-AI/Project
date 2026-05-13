"""
Shared subscription renewal / wallet recharge helpers for Stripe webhooks,
Django admin (Organization, Organizations Management), and staff tools.
"""

from __future__ import annotations

import calendar
from decimal import Decimal

from django.utils import timezone as django_tz


def add_one_calendar_month(base):
    """Return *base* advanced by one calendar month (same day when possible)."""
    month = base.month + 1 if base.month < 12 else 1
    year = base.year if base.month < 12 else base.year + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


def extend_subscription_end_date_one_month(subscription, *, now=None):
    """
    Advance subscription.end_date by one month from max(existing end_date, now).
    Sets status=active and renewed_at=now. Saves the subscription.
    """
    now = now or django_tz.now()
    base = subscription.end_date if subscription.end_date and subscription.end_date > now else now
    subscription.end_date = add_one_calendar_month(base)
    subscription.status = "active"
    subscription.renewed_at = now
    subscription.save(update_fields=["end_date", "status", "renewed_at", "updated_at"])
    return subscription


def recharge_org_wallet_from_credits_usd(organization, credits_usd) -> bool:
    """
    Add compute units to the org wallet from a USD credit budget.
    Returns True if any units were credited, False if credits_usd is falsy or currency missing.
    """
    from api.consumption.models import Currency, OrganizationWallet

    if not credits_usd:
        return False
    currency = Currency.objects.filter(name="Compute Unit").first()
    if not currency:
        return False
    compute_units = Decimal(str(credits_usd)) * Decimal(currency.one_usd_is)
    wallet = OrganizationWallet.objects.filter(organization=organization).first()
    if wallet:
        wallet.recharge(compute_units)
        return True
    OrganizationWallet.objects.create(
        organization=organization,
        balance=compute_units,
        unit=currency,
    )
    return True


def recharge_wallet_for_subscription_credits(subscription) -> bool:
    """Recharge org wallet using subscription effective USD credit limit."""
    credits = subscription.get_effective_credits_limit_usd()
    if credits is None:
        return False
    return recharge_org_wallet_from_credits_usd(subscription.organization, credits)


def renew_subscription_period_and_recharge_wallet(subscription, *, recharge_wallet: bool = True):
    """
    Extend subscription by one month and optionally recharge wallet from plan credits.
    Used by legacy Organization admin renew action.
    """
    extend_subscription_end_date_one_month(subscription)
    if recharge_wallet:
        recharge_wallet_for_subscription_credits(subscription)


def expire_subscription_now(subscription, *, now=None):
    """Mark subscription expired with end_date = now."""
    now = now or django_tz.now()
    subscription.status = "expired"
    subscription.end_date = now
    subscription.save(update_fields=["status", "end_date", "updated_at"])
    return subscription
