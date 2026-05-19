"""
Shared subscription renewal / wallet recharge helpers for Stripe webhooks,
Django admin (Organization, Organizations Management), and staff tools.
"""

from __future__ import annotations

import calendar
from decimal import Decimal

from django.db import transaction
from django.db.models import F
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


def _ledger_tx(
    organization,
    *,
    bucket: str,
    delta: Decimal,
    reason: str,
    subscription=None,
):
    from api.consumption.models import OrganizationWalletTransaction

    OrganizationWalletTransaction.objects.create(
        organization=organization,
        bucket=bucket,
        delta=delta,
        reason=reason,
        subscription=subscription,
    )


def recharge_org_wallet_compute_units(
    organization,
    compute_units: Decimal,
    *,
    bucket: str,
    reason: str,
    subscription=None,
) -> bool:
    """
    Add compute units to the given wallet bucket under row lock.
    Creates wallet if missing. Writes a ledger row when delta is non-zero.
    """
    from api.consumption.models import (
        Currency,
        OrganizationWallet,
        OrganizationWalletTransaction,
    )

    if not compute_units or compute_units <= 0:
        return False
    compute_units = Decimal(compute_units).quantize(Decimal("1.00000000"))
    currency = Currency.objects.filter(name="Compute Unit").first()
    if not currency:
        return False

    field = (
        "subscription_balance"
        if bucket == OrganizationWalletTransaction.BUCKET_SUBSCRIPTION
        else "purchased_balance"
    )

    with transaction.atomic():
        wallet = (
            OrganizationWallet.objects.select_for_update()
            .filter(organization=organization)
            .first()
        )
        if not wallet:
            sub_bal = compute_units if field == "subscription_balance" else Decimal("0")
            pur_bal = compute_units if field == "purchased_balance" else Decimal("0")
            OrganizationWallet.objects.create(
                organization=organization,
                subscription_balance=sub_bal,
                purchased_balance=pur_bal,
                unit=currency,
            )
            _ledger_tx(organization, bucket=bucket, delta=compute_units, reason=reason, subscription=subscription)
            return True

        OrganizationWallet.objects.filter(pk=wallet.pk).update(
            **{field: F(field) + compute_units},
            updated_at=django_tz.now(),
        )
        _ledger_tx(organization, bucket=bucket, delta=compute_units, reason=reason, subscription=subscription)
        return True


def recharge_org_wallet_from_credits_usd(
    organization,
    credits_usd,
    *,
    bucket: str,
    reason: str,
    subscription=None,
) -> bool:
    """
    Add compute units from a USD credit budget into *bucket* (subscription or purchased).
    """
    from api.consumption.models import Currency

    if not credits_usd:
        return False
    currency = Currency.objects.filter(name="Compute Unit").first()
    if not currency:
        return False
    compute_units = Decimal(str(credits_usd)) * Decimal(currency.one_usd_is)
    return recharge_org_wallet_compute_units(
        organization,
        compute_units,
        bucket=bucket,
        reason=reason,
        subscription=subscription,
    )


def recharge_wallet_for_subscription_credits(subscription, *, reason: str | None = None):
    """Recharge org wallet subscription bucket using subscription effective USD credit limit."""
    from api.consumption.models import OrganizationWalletTransaction

    credits = subscription.get_effective_credits_limit_usd()
    if credits is None:
        return False
    r = reason or OrganizationWalletTransaction.REASON_STRIPE_RENEW
    return recharge_org_wallet_from_credits_usd(
        subscription.organization,
        credits,
        bucket=OrganizationWalletTransaction.BUCKET_SUBSCRIPTION,
        reason=r,
        subscription=subscription,
    )


def recharge_purchased_credits_usd(organization, credits_usd, *, reason: str, subscription=None) -> bool:
    from api.consumption.models import OrganizationWalletTransaction

    return recharge_org_wallet_from_credits_usd(
        organization,
        credits_usd,
        bucket=OrganizationWalletTransaction.BUCKET_PURCHASED,
        reason=reason,
        subscription=subscription,
    )


def forfeit_subscription_credits(organization) -> Decimal:
    """
    Zero the subscription bucket for this org (idempotent). Purchased balance unchanged.
    Returns compute units forfeited (0 if already empty / no wallet).
    """
    from api.consumption.models import OrganizationWallet, OrganizationWalletTransaction

    with transaction.atomic():
        wallet = (
            OrganizationWallet.objects.select_for_update()
            .filter(organization=organization)
            .first()
        )
        if not wallet:
            return Decimal("0")
        forfeited = wallet.subscription_balance
        if forfeited <= 0:
            return Decimal("0")
        OrganizationWallet.objects.filter(pk=wallet.pk).update(
            subscription_balance=Decimal("0"),
            updated_at=django_tz.now(),
        )
        _ledger_tx(
            organization,
            bucket=OrganizationWalletTransaction.BUCKET_SUBSCRIPTION,
            delta=-forfeited,
            reason=OrganizationWalletTransaction.REASON_FORFEIT_EXPIRY,
        )
        return forfeited


def renew_subscription_period_and_recharge_wallet(subscription, *, recharge_wallet: bool = True):
    """
    Extend subscription by one month and optionally recharge wallet from plan credits.
    Used by legacy Organization admin renew action.
    """
    extend_subscription_end_date_one_month(subscription)
    if recharge_wallet:
        from api.consumption.models import OrganizationWalletTransaction

        recharge_wallet_for_subscription_credits(
            subscription,
            reason=OrganizationWalletTransaction.REASON_ADMIN_MANUAL_SUB,
        )


def expire_subscription_now(subscription, *, now=None):
    """Mark subscription expired with end_date = now and forfeit subscription-bucket credits."""
    now = now or django_tz.now()
    subscription.status = "expired"
    subscription.end_date = now
    subscription.save(update_fields=["status", "end_date", "updated_at"])
    forfeit_subscription_credits(subscription.organization)
    return subscription
