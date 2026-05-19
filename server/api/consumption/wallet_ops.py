"""Atomic organization wallet balance operations (subscription vs purchased buckets)."""

from __future__ import annotations

from decimal import Decimal

from django.db import transaction

from api.consumption.models import OrganizationWallet


def organization_wallet_use_balance(organization_id, amount: Decimal) -> bool:
    """
    Deduct compute units: subscription bucket first, then purchased.
    Mirrors legacy single-balance semantics: if insufficient total, zero both buckets and return False.
    """
    amount = Decimal(amount).quantize(Decimal("1.00000000"))
    with transaction.atomic():
        w = (
            OrganizationWallet.objects.select_for_update()
            .filter(organization_id=organization_id)
            .first()
        )
        if not w:
            return False
        total = w.subscription_balance + w.purchased_balance
        if total < amount:
            w.subscription_balance = Decimal("0")
            w.purchased_balance = Decimal("0")
            w.save(
                update_fields=["subscription_balance", "purchased_balance", "updated_at"]
            )
            return False
        rem = amount
        take_sub = min(rem, w.subscription_balance)
        w.subscription_balance -= take_sub
        rem -= take_sub
        if rem > 0:
            w.purchased_balance -= rem
        w.save(update_fields=["subscription_balance", "purchased_balance", "updated_at"])
        return True
