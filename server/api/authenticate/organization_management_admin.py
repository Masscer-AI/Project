"""
Django admin: Organizations Management — billing dashboard, manual enterprise
subscriptions, wallet recharge, and organization-level feature flags.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import datetime, time as dt_time, timezone as dt_timezone
from decimal import Decimal, InvalidOperation

import stripe
from django.conf import settings
from django.contrib import admin, messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.utils.translation import gettext as _, ngettext

from api.authenticate.models import (
    FeatureFlag,
    FeatureFlagAssignment,
    Organization,
    OrganizationManagementProxy,
    UserProfile,
)
from api.consumption.models import Currency, OrganizationWallet, OrganizationWalletTransaction
from api.payments.billing_helpers import (
    forfeit_subscription_credits,
    recharge_purchased_credits_usd,
    recharge_wallet_for_subscription_credits,
)
from api.payments.models import Subscription, SubscriptionPayment, SubscriptionPlan


def _cancel_all_masscer_subscriptions_for_org(org: Organization) -> int:
    """Mark every subscription row for this org as cancelled in Masscer (does not call Stripe)."""
    had_active = _masscer_active_subscriptions_qs(org).exists()
    now = timezone.now()
    n = Subscription.objects.filter(organization=org).update(
        status="cancelled",
        end_date=now,
        updated_at=now,
    )
    if had_active:
        forfeit_subscription_credits(org)
    return n


def _parse_optional_decimal(value) -> Decimal | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(_("Invalid decimal: %(value)s") % {"value": repr(value)}) from exc


def _parse_end_datetime(date_str) -> datetime | None:
    if not date_str or not str(date_str).strip():
        return None
    d = parse_date(str(date_str).strip())
    if not d:
        raise ValueError(_("Invalid end date"))
    return timezone.make_aware(datetime.combine(d, dt_time(23, 59, 59)))


def _add_months_clamped(base: datetime, months: int) -> datetime:
    """Add months keeping day where possible; clamp to month end otherwise."""
    month_idx = (base.month - 1) + months
    year = base.year + month_idx // 12
    month = (month_idx % 12) + 1
    day = min(base.day, monthrange(year, month)[1])
    return base.replace(year=year, month=month, day=day)


def _renewed_end_date(base: datetime, billing_interval: str) -> datetime:
    if billing_interval == "monthly":
        return _add_months_clamped(base, 1)
    if billing_interval == "quarterly":
        return _add_months_clamped(base, 3)
    if billing_interval == "yearly":
        return _add_months_clamped(base, 12)
    raise ValueError(_("Only monthly, quarterly, or yearly subscriptions can be renewed."))


def _badge_label(code: str) -> str:
    labels = {
        "no_wallet": _("No wallet"),
        "low_balance": _("Low balance"),
        "inactive_sub": _("Inactive subscription"),
        "pending_payment": _("Pending payment"),
        "no_subscription": _("No subscription"),
    }
    return labels.get(code, code)


def _stripe_error_is_unknown_subscription(exc: BaseException) -> bool:
    """True when Stripe says the subscription id does not exist (deleted, wrong account, etc.)."""
    code = getattr(exc, "code", None)
    if code == "resource_missing":
        return True
    err = getattr(exc, "error", None)
    if isinstance(err, dict) and err.get("code") == "resource_missing":
        return True
    if "no such subscription" in str(exc).lower():
        return True
    return False


def _clear_matching_stripe_subscription_id(stripe_subscription_id: str) -> int:
    """Clear stale Stripe subscription id from all Masscer rows pointing at it."""
    sid = (stripe_subscription_id or "").strip()
    if not sid:
        return 0
    return Subscription.objects.filter(stripe_subscription_id=sid).update(
        stripe_subscription_id=None,
        updated_at=timezone.now(),
    )


def _stripe_live_view(stripe_subscription_id: str) -> dict:
    """Live Stripe subscription fields for admin (read-only)."""
    base = {
        "configured": bool(getattr(settings, "STRIPE_SECRET_KEY", "")),
        "ok": False,
        "error": None,
        "stripe_status": None,
        "cancel_at_period_end": False,
        "cancel_at_display": None,
        "current_period_end_display": None,
    }
    sid = (stripe_subscription_id or "").strip()
    if not sid:
        base["error"] = _("No Stripe subscription id on this row.")
        return base
    if not base["configured"]:
        base["error"] = _("STRIPE_SECRET_KEY is not configured.")
        return base
    stripe.api_key = settings.STRIPE_SECRET_KEY
    try:
        sub = stripe.Subscription.retrieve(sid)
    except stripe.StripeError as exc:
        if _stripe_error_is_unknown_subscription(exc):
            cleared = _clear_matching_stripe_subscription_id(sid)
            out = {**base}
            out["cleared_stale_id"] = True
            out["cleared_rows"] = cleared
            out["error"] = None
            return out
        out = {**base}
        out["error"] = str(exc)
        return out
    cancel_at_ts = sub.get("cancel_at")
    cancel_at_display = None
    if cancel_at_ts:
        cancel_at_display = datetime.fromtimestamp(
            cancel_at_ts, tz=dt_timezone.utc
        ).strftime("%Y-%m-%d %H:%M UTC")
    cpe = sub.get("current_period_end")
    cpe_display = None
    if cpe:
        cpe_display = datetime.fromtimestamp(cpe, tz=dt_timezone.utc).strftime(
            "%Y-%m-%d %H:%M UTC"
        )
    return {
        "configured": True,
        "ok": True,
        "error": None,
        "stripe_status": sub.get("status"),
        "cancel_at_period_end": bool(sub.get("cancel_at_period_end")),
        "cancel_at_display": cancel_at_display,
        "current_period_end_display": cpe_display,
    }


_STRIPE_SUBSCRIPTION_TERMINAL = frozenset({"canceled", "incomplete_expired"})


def _masscer_active_subscriptions_qs(org: Organization):
    """Rows where the org can still use plan benefits (same rule as Subscription.is_active())."""
    now = timezone.now()
    return Subscription.objects.filter(
        organization=org,
        status__in=("trial", "active"),
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=now))


def _split_stripe_subscription_rows_for_cancel_ui(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Rows that still accept Stripe cancel API vs informational-only rows."""
    active_cancel: list[dict] = []
    other: list[dict] = []
    for row in rows:
        live = row["live"]
        s = row["subscription"]
        sid = (s.stripe_subscription_id or "").strip()
        configured = bool(live.get("configured"))
        ok = bool(live.get("ok"))
        stripe_status = (live.get("stripe_status") or "").lower()
        terminal_in_stripe = ok and stripe_status in _STRIPE_SUBSCRIPTION_TERMINAL
        show_cancel = bool(configured and sid and not terminal_in_stripe)
        if show_cancel:
            active_cancel.append(row)
        else:
            other.append(row)
    return active_cancel, other


def _stripe_subscription_rows_for_org(org):
    subs = list(
        Subscription.objects.filter(organization=org)
        .exclude(Q(stripe_subscription_id__isnull=True) | Q(stripe_subscription_id=""))
        .select_related("plan")
        .order_by("-created_at")
    )
    rows = []
    stale_rows_cleared = 0
    for s in subs:
        sid = (s.stripe_subscription_id or "").strip()
        if not sid:
            continue
        live = _stripe_live_view(sid)
        if live.get("cleared_stale_id"):
            stale_rows_cleared += int(live.get("cleared_rows") or 0)
            continue
        rows.append({"subscription": s, "live": live})
    return rows, stale_rows_cleared


def _stripe_cancel_at_period_end(stripe_subscription_id: str) -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY
    stripe.Subscription.modify(stripe_subscription_id, cancel_at_period_end=True)


def _stripe_cancel_immediately(stripe_subscription_id: str) -> None:
    stripe.api_key = settings.STRIPE_SECRET_KEY
    if hasattr(stripe.Subscription, "cancel"):
        stripe.Subscription.cancel(stripe_subscription_id)
    else:
        stripe.Subscription.delete(stripe_subscription_id)


@admin.register(OrganizationManagementProxy)
class OrganizationManagementProxyAdmin(admin.ModelAdmin):
    """Custom changelist + per-organization billing detail (not default CRUD)."""

    change_list_template = "admin/organization_management/change_list.html"

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.is_staff

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_module_permission(self, request):
        return request.user.is_staff

    def get_urls(self):
        urls = super().get_urls()
        opts = self.model._meta
        custom = [
            path(
                "<uuid:object_id>/billing/",
                self.admin_site.admin_view(self.billing_detail_view),
                name=f"{opts.app_label}_{opts.model_name}_billing",
            ),
        ]
        return custom + urls

    def changelist_view(self, request, extra_context=None):
        if not self.has_view_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Organizations Management"),
            "org_rows": self._organization_rows(request),
            "q": (request.GET.get("q") or "").strip(),
            "has_add_permission": self.has_add_permission(request),
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(request, self.change_list_template, context)

    def _organization_rows(self, request):
        qs = (
            Organization.objects.select_related("owner")
            .annotate(member_count=Count("members", distinct=True))
            .order_by("name")
        )
        q = (request.GET.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(owner__username__icontains=q)
                | Q(owner__email__icontains=q)
            )
        rows = []
        for org in qs[:500]:
            latest = (
                Subscription.objects.filter(organization=org)
                .select_related("plan")
                .order_by("-created_at")
                .first()
            )
            try:
                wallet = org.wallet
            except OrganizationWallet.DoesNotExist:
                wallet = None
            usd_balance = None
            if wallet and wallet.unit_id:
                usd_balance = float(wallet.total_balance) / float(wallet.unit.one_usd_is)
            badge_codes = []
            if not wallet:
                badge_codes.append("no_wallet")
            elif wallet.total_balance <= 0:
                badge_codes.append("low_balance")
            if latest:
                if not latest.is_active():
                    badge_codes.append("inactive_sub")
                if latest.status == "pending_payment":
                    badge_codes.append("pending_payment")
            else:
                badge_codes.append("no_subscription")
            rows.append(
                {
                    "org": org,
                    "latest_subscription": latest,
                    "wallet_usd": usd_balance,
                    "member_count": getattr(org, "member_count", 0) or 0,
                    "badges": [_badge_label(c) for c in badge_codes],
                }
            )
        return rows

    def billing_detail_view(self, request, object_id):
        org = get_object_or_404(Organization, pk=object_id)
        if not self.has_view_permission(request):
            from django.core.exceptions import PermissionDenied

            raise PermissionDenied
        if request.method == "POST":
            action = request.POST.get("action")
            try:
                if action == "manual_subscription":
                    self._post_manual_subscription(request, org)
                elif action == "wallet_recharge":
                    self._post_wallet_recharge(request, org)
                elif action == "toggle_feature":
                    self._post_toggle_feature(request, org)
                elif action == "stripe_cancel_at_period_end":
                    self._post_stripe_cancel_at_period_end(request, org)
                elif action == "stripe_cancel_immediately":
                    self._post_stripe_cancel_immediately(request, org)
                elif action == "renew_subscription":
                    self._post_renew_subscription(request, org)
                else:
                    messages.error(request, _("Unknown action."))
            except ValueError as exc:
                messages.error(request, str(exc))
            except stripe.StripeError as exc:
                messages.error(request, _("Stripe error: %(msg)s") % {"msg": exc})
            return HttpResponseRedirect(request.path)
        return self._billing_get(request, org)

    def _billing_get(self, request, org):
        latest = (
            Subscription.objects.filter(organization=org)
            .select_related("plan")
            .order_by("-created_at")
            .first()
        )
        try:
            wallet = org.wallet
        except OrganizationWallet.DoesNotExist:
            wallet = None
        manual_subscription_plans = list(
            SubscriptionPlan.objects.filter(slug="custom").order_by("slug")
        )
        # Only flags that are defined as organization-level (not user-only product flags).
        feature_flags = FeatureFlag.objects.filter(organization_only=True).order_by("name")
        assignments = {
            a.feature_flag_id: a
            for a in FeatureFlagAssignment.objects.filter(
                organization=org, user__isnull=True
            )
        }
        feature_flag_rows = []
        for flag in feature_flags:
            a = assignments.get(flag.id)
            feature_flag_rows.append(
                {
                    "flag": flag,
                    "enabled": a.enabled if a else False,
                }
            )
        member_count = UserProfile.objects.filter(organization=org).count()
        wallet_balance_usd = None
        if wallet and wallet.unit_id:
            wallet_balance_usd = float(wallet.total_balance) / float(wallet.unit.one_usd_is)
        cu_currency = Currency.objects.filter(name="Compute Unit").first()
        if wallet and wallet.unit_id:
            wallet_modal_balance_cu = str(wallet.total_balance)
            wallet_modal_subscription_balance_cu = str(wallet.subscription_balance)
            wallet_modal_purchased_balance_cu = str(wallet.purchased_balance)
            wallet_modal_one_usd_is = str(wallet.unit.one_usd_is)
            wallet_modal_unit_name = wallet.unit.name
        else:
            wallet_modal_balance_cu = "0"
            wallet_modal_subscription_balance_cu = "0"
            wallet_modal_purchased_balance_cu = "0"
            wallet_modal_one_usd_is = (
                str(cu_currency.one_usd_is) if cu_currency else ""
            )
            wallet_modal_unit_name = (
                cu_currency.name if cu_currency else "Compute Unit"
            )
        subscription_payments = list(
            SubscriptionPayment.objects.filter(subscription__organization=org)
            .select_related("subscription", "subscription__plan")
            .order_by("-created_at")[:200]
        )
        stripe_subscription_rows, stale_stripe_rows_cleared = _stripe_subscription_rows_for_org(
            org
        )
        stripe_subscription_rows_active, _stripe_subscription_rows_other = (
            _split_stripe_subscription_rows_for_cancel_ui(stripe_subscription_rows)
        )
        if stale_stripe_rows_cleared:
            latest = (
                Subscription.objects.filter(organization=org)
                .select_related("plan")
                .order_by("-created_at")
                .first()
            )
            messages.info(
                request,
                ngettext(
                    "Stripe reported missing subscription id(s); cleared stale "
                    "stripe_subscription_id from one Masscer row.",
                    "Stripe reported missing subscription id(s); cleared stale "
                    "stripe_subscription_id from %(count)d Masscer rows.",
                    stale_stripe_rows_cleared,
                )
                % {"count": stale_stripe_rows_cleared},
            )
        all_masscer_subscriptions = list(
            Subscription.objects.filter(organization=org)
            .select_related("plan")
            .order_by("-created_at")
        )
        stripe_live_by_subscription_id = {
            str(row["subscription"].id): row["live"] for row in stripe_subscription_rows
        }
        stripe_cancellable_subscription_ids = {
            str(row["subscription"].id) for row in stripe_subscription_rows_active
        }
        masscer_subscription_rows = []
        for sub in all_masscer_subscriptions:
            sub_id = str(sub.id)
            masscer_subscription_rows.append(
                {
                    "subscription": sub,
                    "stripe_live": stripe_live_by_subscription_id.get(sub_id),
                    "show_stripe_cancel_actions": sub_id
                    in stripe_cancellable_subscription_ids,
                }
            )
        masscer_subscriptions_active = [
            row
            for row in masscer_subscription_rows
            if row["subscription"].is_active()
            or row["subscription"].status == "expired"
        ]
        masscer_subscriptions_inactive = [
            row for row in masscer_subscription_rows if not row["subscription"].is_active()
        ]
        latest_is_stripe = bool(
            latest
            and latest.payment_method == "stripe"
            and (latest.stripe_subscription_id or "").strip()
        )
        has_stripe_subscription_on_file = bool(stripe_subscription_rows)
        masscer_active_subscription_count = _masscer_active_subscriptions_qs(org).count()
        wallet_recharge_allowed = masscer_active_subscription_count > 0
        changelist_url = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist"
        )
        billing_url = reverse(
            f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_billing",
            args=[org.pk],
        )
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": _("Billing: %(name)s") % {"name": org.name},
            "organization": org,
            "latest_subscription": latest,
            "wallet": wallet,
            "manual_subscription_plans": manual_subscription_plans,
            "has_manual_subscription_plan": bool(manual_subscription_plans),
            "feature_flags": feature_flags,
            "feature_flag_rows": feature_flag_rows,
            "member_count": member_count,
            "changelist_url": changelist_url,
            "billing_url": billing_url,
            "subscription_status_choices": Subscription.STATUS_CHOICES,
            "billing_interval_choices": Subscription.BILLING_INTERVAL_CHOICES,
            "wallet_balance_usd": wallet_balance_usd,
            "wallet_modal_balance_cu": wallet_modal_balance_cu,
            "wallet_modal_subscription_balance_cu": wallet_modal_subscription_balance_cu,
            "wallet_modal_purchased_balance_cu": wallet_modal_purchased_balance_cu,
            "wallet_modal_one_usd_is": wallet_modal_one_usd_is,
            "wallet_modal_unit_name": wallet_modal_unit_name,
            "subscription_payments": subscription_payments,
            "masscer_subscriptions_active": masscer_subscriptions_active,
            "masscer_subscriptions_inactive": masscer_subscriptions_inactive,
            "latest_is_stripe": latest_is_stripe,
            "has_stripe_subscription_on_file": has_stripe_subscription_on_file,
            "masscer_active_subscription_count": masscer_active_subscription_count,
            "wallet_recharge_allowed": wallet_recharge_allowed,
        }
        request.current_app = self.admin_site.name
        return TemplateResponse(
            request, "admin/organization_management/billing_detail.html", context
        )

    def _post_manual_subscription(self, request, org):
        plan_id = request.POST.get("plan_id")
        if not plan_id:
            raise ValueError(_("Plan is required."))
        plan = SubscriptionPlan.objects.filter(pk=plan_id).first()
        if not plan:
            raise ValueError(_("Invalid plan."))
        if plan.slug != "custom":
            raise ValueError(
                _("Manual subscriptions from this page must use the custom catalog plan.")
            )

        if request.POST.get("confirm_manual_subscription_revokes_previous") != "on":
            raise ValueError(
                _(
                    "Check the box to confirm that all existing Masscer subscription "
                    "rows for this organization will be marked cancelled before creating "
                    "a new manual subscription."
                )
            )

        status = request.POST.get("status") or "active"
        valid_status = {c[0] for c in Subscription.STATUS_CHOICES}
        if status not in valid_status:
            raise ValueError(_("Invalid subscription status."))

        billing_interval = request.POST.get("billing_interval") or "monthly"
        valid_interval = {c[0] for c in Subscription.BILLING_INTERVAL_CHOICES}
        if billing_interval not in valid_interval:
            raise ValueError(_("Invalid billing interval."))

        end_date = _parse_end_datetime(request.POST.get("end_date"))
        credits_limit_usd = _parse_optional_decimal(request.POST.get("credits_limit_usd"))
        contract_price_usd = _parse_optional_decimal(request.POST.get("contract_price_usd"))
        if credits_limit_usd is None:
            raise ValueError(
                _("Credit budget (USD) is required for manual custom subscriptions.")
            )
        if credits_limit_usd < 0:
            raise ValueError(_("Credit budget (USD) cannot be negative."))
        if contract_price_usd is None:
            raise ValueError(
                _("Contract price (USD) is required for manual custom subscriptions.")
            )
        if contract_price_usd < 0:
            raise ValueError(_("Contract price (USD) cannot be negative."))
        internal_notes = (request.POST.get("internal_notes") or "").strip() or None
        recharge_wallet = request.POST.get("recharge_wallet") == "on"

        cancelled = _cancel_all_masscer_subscriptions_for_org(org)
        sub = Subscription.objects.create(
            organization=org,
            plan=plan,
            status=status,
            payment_method="manual",
            end_date=end_date,
            credits_limit_usd=credits_limit_usd,
            contract_price_usd=contract_price_usd,
            billing_interval=billing_interval,
            internal_notes=internal_notes,
            stripe_subscription_id=None,
            stripe_customer_id=None,
        )
        if cancelled:
            messages.success(
                request,
                ngettext(
                    "Marked one previous Masscer subscription row as cancelled; created new manual subscription.",
                    "Marked %(count)d previous Masscer subscription rows as cancelled; created new manual subscription.",
                    cancelled,
                )
                % {"count": cancelled},
            )
        else:
            messages.success(request, _("Created new manual subscription."))

        if recharge_wallet:
            if recharge_wallet_for_subscription_credits(
                sub,
                reason=OrganizationWalletTransaction.REASON_ADMIN_MANUAL_SUB,
            ):
                messages.success(
                    request,
                    _("Wallet recharged from subscription credit budget."),
                )
            else:
                messages.warning(
                    request,
                    _(
                        "Recharge skipped: no USD credit budget configured for this subscription."
                    ),
                )

    def _post_wallet_recharge(self, request, org):
        amount = _parse_optional_decimal(request.POST.get("amount_usd"))
        if amount is None or amount <= 0:
            raise ValueError(_("Enter a positive amount_usd for wallet recharge."))
        active_subs_qs = _masscer_active_subscriptions_qs(org)
        if not active_subs_qs.exists():
            raise ValueError(
                _("Wallet recharge requires at least one active Masscer subscription.")
            )
        register_payment = request.POST.get("register_wallet_recharge_payment") == "on"
        payment_amount = None
        payment_note = None
        sub_for_payment = None
        if register_payment:
            payment_note = (request.POST.get("wallet_recharge_payment_note") or "").strip()
            if not payment_note:
                raise ValueError(_("Payment note is required when registering a payment."))
            payment_amount = amount.quantize(Decimal("0.01"))
            if payment_amount != amount:
                raise ValueError(
                    _("Use no more than two decimal places when registering a payment.")
                )
            sub_for_payment = active_subs_qs.order_by("-created_at").select_related("plan").first()
        if recharge_purchased_credits_usd(
            org,
            amount,
            reason=OrganizationWalletTransaction.REASON_ADMIN_RECHARGE,
            subscription=sub_for_payment,
        ):
            messages.success(
                request,
                _("Wallet credited with %(amount)s USD equivalent.") % {"amount": amount},
            )
            if register_payment and sub_for_payment:
                SubscriptionPayment.objects.create(
                    subscription=sub_for_payment,
                    amount_usd=payment_amount,
                    method="manual",
                    status="completed",
                    notes=payment_note,
                )
                messages.success(
                    request,
                    _("Registered wallet recharge as a payment."),
                )
        else:
            messages.error(
                request,
                _("Could not recharge wallet (Compute Unit currency missing?)."),
            )

    def _post_toggle_feature(self, request, org):
        raw_id = request.POST.get("feature_flag_id")
        if not raw_id:
            raise ValueError(_("Missing feature_flag_id."))
        try:
            flag_id = int(raw_id)
        except (TypeError, ValueError) as exc:
            raise ValueError(_("Invalid feature_flag_id.")) from exc
        enabled = request.POST.get("enabled", "").lower()
        if enabled not in ("true", "false"):
            raise ValueError(_("Invalid enabled value."))
        enabled = enabled == "true"
        flag = FeatureFlag.objects.filter(pk=flag_id, organization_only=True).first()
        if not flag:
            raise ValueError(_("Unknown or non-organization feature flag."))
        FeatureFlagAssignment.objects.update_or_create(
            organization=org,
            feature_flag=flag,
            defaults={"enabled": enabled, "user": None},
        )
        messages.success(
            request,
            _("Feature flag '%(name)s' set to %(state)s.")
            % {"name": flag.name, "state": _("On") if enabled else _("Off")},
        )

    def _subscription_for_org_stripe_action(self, org, pk_raw):
        try:
            pk = uuid.UUID(str(pk_raw))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(_("Invalid Masscer subscription id.")) from exc
        sub = Subscription.objects.filter(pk=pk, organization=org).first()
        if not sub:
            raise ValueError(_("Subscription not found for this organization."))
        sid = (sub.stripe_subscription_id or "").strip()
        if not sid:
            raise ValueError(_("That subscription row has no Stripe subscription id."))
        return sub, sid

    def _subscription_for_org_action(self, org, pk_raw):
        try:
            pk = uuid.UUID(str(pk_raw))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(_("Invalid Masscer subscription id.")) from exc
        sub = Subscription.objects.filter(pk=pk, organization=org).select_related("plan").first()
        if not sub:
            raise ValueError(_("Subscription not found for this organization."))
        return sub

    @transaction.atomic
    def _post_renew_subscription(self, request, org):
        if request.POST.get("confirm_manual_renewal") != "on":
            raise ValueError(
                _('Check "I confirm manual renewal" before renewing this subscription.')
            )
        sub = self._subscription_for_org_action(org, request.POST.get("masscer_subscription_id"))
        if sub.billing_interval in ("one_time", "custom"):
            raise ValueError(_("This subscription interval is not renewable from admin."))
        if sub.status not in ("active", "expired"):
            raise ValueError(
                _("Only active or expired subscriptions can be renewed from admin.")
            )

        now = timezone.now()
        old_end_date = sub.end_date
        if sub.status == "active" and sub.end_date and sub.end_date >= now:
            renewal_base = sub.end_date
        else:
            renewal_base = now
        sub.end_date = _renewed_end_date(renewal_base, sub.billing_interval)
        sub.status = "active"
        sub.save(update_fields=["status", "end_date", "updated_at"])

        if not recharge_wallet_for_subscription_credits(
            sub,
            reason=OrganizationWalletTransaction.REASON_ADMIN_MANUAL_SUB,
        ):
            raise ValueError(
                _("Could not recharge wallet from this subscription's USD credit budget.")
            )

        payment_amount = (sub.get_display_monthly_price_usd() or Decimal("0")).quantize(
            Decimal("0.01")
        )
        SubscriptionPayment.objects.create(
            subscription=sub,
            amount_usd=payment_amount,
            method="manual",
            status="completed",
            notes=_(
                "Manual renewal in admin. Previous end: %(old)s. New end: %(new)s."
            )
            % {
                "old": old_end_date.isoformat() if old_end_date else "—",
                "new": sub.end_date.isoformat() if sub.end_date else "—",
            },
        )
        messages.success(
            request,
            _("Subscription renewed. End date extended, wallet recharged, and payment registered."),
        )

    def _post_stripe_cancel_at_period_end(self, request, org):
        if request.POST.get("confirm_stripe_cancel") != "on":
            raise ValueError(
                _('Check "I confirm this Stripe change" before cancelling in Stripe.')
            )
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError(_("Stripe is not configured (STRIPE_SECRET_KEY)."))
        _sub, sid = self._subscription_for_org_stripe_action(
            org, request.POST.get("masscer_subscription_id")
        )
        try:
            _stripe_cancel_at_period_end(sid)
        except stripe.StripeError as exc:
            if _stripe_error_is_unknown_subscription(exc):
                n = _clear_matching_stripe_subscription_id(sid)
                messages.success(
                    request,
                    ngettext(
                        "This Stripe subscription no longer exists (removed or expired). "
                        "Cleared stale stripe_subscription_id from one Masscer row.",
                        "This Stripe subscription no longer exists (removed or expired). "
                        "Cleared stale stripe_subscription_id from %(count)d Masscer rows.",
                        n,
                    )
                    % {"count": n},
                )
                return
            raise
        messages.success(
            request,
            _(
                "Stripe will cancel this subscription at the end of the current billing period. "
                "The row in Masscer may stay active until Stripe webhooks run."
            ),
        )

    def _post_stripe_cancel_immediately(self, request, org):
        if request.POST.get("confirm_stripe_cancel") != "on":
            raise ValueError(
                _('Check "I confirm this Stripe change" before cancelling in Stripe.')
            )
        if not settings.STRIPE_SECRET_KEY:
            raise ValueError(_("Stripe is not configured (STRIPE_SECRET_KEY)."))
        sub, sid = self._subscription_for_org_stripe_action(
            org, request.POST.get("masscer_subscription_id")
        )
        try:
            _stripe_cancel_immediately(sid)
        except stripe.StripeError as exc:
            if _stripe_error_is_unknown_subscription(exc):
                n = _clear_matching_stripe_subscription_id(sid)
                messages.success(
                    request,
                    ngettext(
                        "This Stripe subscription no longer exists (removed or expired). "
                        "Cleared stale stripe_subscription_id from one Masscer row.",
                        "This Stripe subscription no longer exists (removed or expired). "
                        "Cleared stale stripe_subscription_id from %(count)d Masscer rows.",
                        n,
                    )
                    % {"count": n},
                )
                return
            raise
        sub.refresh_from_db()
        sub.status = "cancelled"
        sub.save(update_fields=["status", "updated_at"])
        forfeit_subscription_credits(org)
        messages.success(
            request,
            _(
                "Stripe subscription cancelled immediately. This Masscer subscription row was marked cancelled."
            ),
        )
