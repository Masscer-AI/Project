import json
from datetime import datetime, timezone
import stripe
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse, HttpResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone as tz

from api.authenticate.decorators.token_required import token_required
from api.authenticate.models import Organization
from api.payments.models import Subscription, SubscriptionPlan
from api.consumption.models import OrganizationWallet, Currency

stripe.api_key = settings.STRIPE_SECRET_KEY

# Maps our plan slugs to Stripe Price IDs configured in settings
PLAN_SLUG_TO_STRIPE_PRICE = {
    "organization": settings.STRIPE_PRICE_ORGANIZATION,
}

# Fixed one-time credit packages:
# purchase amount (USD) -> credited wallet amount (USD)
CREDIT_PACKAGE_CREDITS_USD = {
    50: 45,
    100: 93,
    200: 190,
}


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationBillingView(View):
    def get(self, request, organization_id, *args, **kwargs):
        try:
            org = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=404)

        if org.owner != request.user:
            return JsonResponse({"error": "Forbidden"}, status=403)

        subscription = (
            Subscription.objects.select_related("plan")
            .filter(organization=org)
            .order_by("-created_at")
            .first()
        )

        wallet = OrganizationWallet.objects.select_related("unit").filter(organization=org).first()

        subscription_data = None
        if subscription:
            subscription_data = {
                "id": str(subscription.id),
                "status": subscription.status,
                "payment_method": subscription.payment_method,
                "is_active": subscription.is_active(),
                "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
                "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
                "plan": {
                    "slug": subscription.plan.slug,
                    "display_name": subscription.plan.display_name,
                    "monthly_price_usd": str(subscription.plan.monthly_price_usd),
                    "credits_limit_usd": str(subscription.plan.credits_limit_usd) if subscription.plan.credits_limit_usd is not None else None,
                    "duration_days": subscription.plan.duration_days,
                },
            }
            subscription_data.update(_get_stripe_subscription_state(subscription))

        wallet_data = None
        if wallet:
            wallet_data = {
                "balance": str(wallet.balance),
                "unit_name": wallet.unit.name,
                "one_usd_is": wallet.unit.one_usd_is,
                "balance_usd": str(
                    round(float(wallet.balance) / wallet.unit.one_usd_is, 4)
                ),
            }

        return JsonResponse({
            "subscription": subscription_data,
            "wallet": wallet_data,
        })


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class CreateCheckoutSessionView(View):
    """
    POST /v1/payments/organizations/<org_id>/checkout/
    Body: { "plan_slug": "organization" }

    Creates a Stripe Checkout Session and returns the URL to redirect the user to.
    """

    def post(self, request, organization_id, *args, **kwargs):
        try:
            org = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=404)

        if org.owner != request.user:
            return JsonResponse({"error": "Forbidden"}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        plan_slug = data.get("plan_slug", "organization")
        price_id = PLAN_SLUG_TO_STRIPE_PRICE.get(plan_slug)
        if not price_id:
            return JsonResponse({"error": f"No Stripe price configured for plan '{plan_slug}'"}, status=400)

        # Reuse existing Stripe customer if we already have one
        existing_sub = Subscription.objects.filter(
            organization=org, stripe_customer_id__isnull=False
        ).order_by("-created_at").first()
        customer_id = existing_sub.stripe_customer_id if existing_sub else None

        frontend_url = settings.FRONTEND_URL or "http://localhost"
        success_url = f"{frontend_url}/organization?billing=success&session_id={{CHECKOUT_SESSION_ID}}"
        cancel_url = f"{frontend_url}/organization?billing=cancelled"

        session_kwargs = {
            "mode": "subscription",
            "line_items": [{"price": price_id, "quantity": 1}],
            "success_url": success_url,
            "cancel_url": cancel_url,
            "metadata": {
                "organization_id": str(org.id),
                "plan_slug": plan_slug,
            },
        }
        if customer_id:
            session_kwargs["customer"] = customer_id
        else:
            session_kwargs["customer_email"] = request.user.email

        try:
            session = stripe.checkout.Session.create(**session_kwargs)
        except stripe.StripeError as e:
            return JsonResponse({"error": str(e)}, status=502)

        return JsonResponse({"checkout_url": session.url})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class CreateBillingPortalSessionView(View):
    """
    POST /v1/payments/organizations/<org_id>/billing-portal/

    Creates a Stripe Billing Portal session so users can manage/cancel subscriptions.
    """

    def post(self, request, organization_id, *args, **kwargs):
        try:
            org = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=404)

        if org.owner != request.user:
            return JsonResponse({"error": "Forbidden"}, status=403)

        latest_sub = (
            Subscription.objects.filter(organization=org, stripe_customer_id__isnull=False)
            .order_by("-created_at")
            .first()
        )
        customer_id = latest_sub.stripe_customer_id if latest_sub else None
        if not customer_id:
            return JsonResponse(
                {"error": "No Stripe customer found for this organization."},
                status=400,
            )

        frontend_url = settings.FRONTEND_URL or "http://localhost"
        return_url = f"{frontend_url}/organization?billing=portal_return"

        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=return_url,
            )
        except stripe.StripeError as e:
            return JsonResponse({"error": str(e)}, status=502)

        return JsonResponse({"portal_url": session.url})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ReactivateSubscriptionView(View):
    """
    POST /v1/payments/organizations/<org_id>/subscriptions/reactivate/

    Clears cancel_at_period_end for an active Stripe subscription.
    """

    def post(self, request, organization_id, *args, **kwargs):
        try:
            org = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=404)

        if org.owner != request.user:
            return JsonResponse({"error": "Forbidden"}, status=403)

        sub = (
            Subscription.objects.filter(
                organization=org,
                payment_method="stripe",
                stripe_subscription_id__isnull=False,
            )
            .order_by("-created_at")
            .first()
        )
        if not sub or not sub.stripe_subscription_id:
            return JsonResponse({"error": "No Stripe subscription found."}, status=400)

        try:
            stripe.Subscription.modify(
                sub.stripe_subscription_id,
                cancel_at_period_end=False,
            )
        except stripe.StripeError as e:
            return JsonResponse({"error": str(e)}, status=502)

        sub.status = "active"
        sub.save(update_fields=["status", "updated_at"])
        return JsonResponse({"ok": True})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class BuyCreditsView(View):
    """
    POST /v1/payments/organizations/<org_id>/buy-credits/
    Body: { "amount_usd": 50 | 100 | 200 }

    Creates a one-time Stripe Checkout Session to purchase compute credits.
    """

    def post(self, request, organization_id, *args, **kwargs):
        try:
            org = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=404)

        if org.owner != request.user:
            return JsonResponse({"error": "Forbidden"}, status=403)

        latest_sub = (
            Subscription.objects.select_related("plan")
            .filter(organization=org)
            .order_by("-created_at")
            .first()
        )
        if (
            not latest_sub
            or not latest_sub.is_active()
            or latest_sub.plan.slug != "organization"
        ):
            return JsonResponse(
                {"error": "Active Organization subscription required to buy credits."},
                status=403,
            )

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        try:
            amount_usd = int(data.get("amount_usd", 0))
        except (TypeError, ValueError):
            return JsonResponse({"error": "amount_usd must be an integer"}, status=400)

        credits_usd = CREDIT_PACKAGE_CREDITS_USD.get(amount_usd)
        if credits_usd is None:
            return JsonResponse(
                {"error": f"amount_usd must be one of: {', '.join(map(str, sorted(CREDIT_PACKAGE_CREDITS_USD.keys())))}"},
                status=400,
            )

        product_id = settings.STRIPE_PRODUCT_CREDITS
        if not product_id:
            return JsonResponse({"error": "Credits product not configured"}, status=500)

        frontend_url = settings.FRONTEND_URL or "http://localhost"
        success_url = f"{frontend_url}/organization?billing=credits_success"
        cancel_url = f"{frontend_url}/organization?billing=credits_cancelled"

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=[{
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": amount_usd * 100,  # Stripe uses cents
                        "product": product_id,
                    },
                    "quantity": 1,
                }],
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={
                    "type": "credit_purchase",
                    "organization_id": str(org.id),
                    "amount_usd": str(amount_usd),
                    "credits_usd": str(credits_usd),
                },
            )
        except stripe.StripeError as e:
            return JsonResponse({"error": str(e)}, status=502)

        return JsonResponse({"checkout_url": session.url})


@csrf_exempt
def stripe_webhook(request):
    """
    POST /v1/payments/webhook/
    Handles Stripe webhook events to keep subscriptions in sync.
    """
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except (ValueError, stripe.SignatureVerificationError) as e:
        return HttpResponse(str(e), status=400)

    # Idempotency guard for Stripe webhook retries/duplicates.
    event_id = event.get("id")
    if event_id:
        cache_key = f"stripe_webhook_event:{event_id}"
        if not cache.add(cache_key, True, timeout=60 * 60 * 24 * 14):
            return HttpResponse(status=200)

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data)

    elif event_type in ("invoice.paid",):
        _handle_invoice_paid(data)

    elif event_type in ("customer.subscription.deleted", "customer.subscription.paused"):
        _handle_subscription_cancelled(data)

    elif event_type == "customer.subscription.updated":
        _handle_subscription_updated(data)

    elif event_type == "invoice.payment_failed":
        _handle_payment_failed(data)

    return HttpResponse(status=200)


def _handle_checkout_completed(session):
    """Route to the right handler based on metadata.type."""
    if session.get("metadata", {}).get("type") == "credit_purchase":
        _handle_credit_purchase_completed(session)
    else:
        _handle_subscription_checkout_completed(session)


def _handle_credit_purchase_completed(session):
    """One-time credit purchase → recharge org wallet."""
    from decimal import Decimal

    org_id = session.get("metadata", {}).get("organization_id")
    amount_usd = session.get("metadata", {}).get("amount_usd")
    credits_usd = session.get("metadata", {}).get("credits_usd")
    if not org_id:
        return

    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return

    currency = Currency.objects.filter(name="Compute Unit").first()
    if not currency:
        return

    credited_usd = credits_usd or amount_usd
    if not credited_usd:
        return

    compute_units = Decimal(credited_usd) * Decimal(currency.one_usd_is)
    wallet = OrganizationWallet.objects.filter(organization=org).first()
    if wallet:
        wallet.recharge(compute_units)


def _handle_subscription_checkout_completed(session):
    """Checkout completed → activate subscription and seed wallet."""
    from decimal import Decimal
    import calendar

    org_id = session.get("metadata", {}).get("organization_id")
    plan_slug = session.get("metadata", {}).get("plan_slug", "organization")
    stripe_sub_id = session.get("subscription")
    stripe_customer_id = session.get("customer")

    if not org_id:
        return

    try:
        org = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return

    plan = SubscriptionPlan.objects.filter(slug=plan_slug).first()
    if not plan:
        return

    now = tz.now()
    next_month = now.month + 1 if now.month < 12 else 1
    next_year = now.year if now.month < 12 else now.year + 1
    day = min(now.day, calendar.monthrange(next_year, next_month)[1])
    end_date = now.replace(year=next_year, month=next_month, day=day)

    sub, _ = Subscription.objects.update_or_create(
        organization=org,
        defaults={
            "plan": plan,
            "status": "active",
            "payment_method": "stripe",
            "stripe_subscription_id": stripe_sub_id,
            "stripe_customer_id": stripe_customer_id,
            "start_date": now,
            "end_date": end_date,
        },
    )

    # Seed / recharge the org wallet
    credits_usd = sub.get_effective_credits_limit_usd()
    if credits_usd:
        currency = Currency.objects.filter(name="Compute Unit").first()
        if currency:
            compute_units = Decimal(credits_usd) * Decimal(currency.one_usd_is)
            wallet, created = OrganizationWallet.objects.get_or_create(
                organization=org,
                defaults={"balance": compute_units, "unit": currency},
            )
            if not created:
                wallet.recharge(compute_units)


def _handle_invoice_paid(invoice):
    """Recurring invoice paid → renew subscription end_date and recharge wallet."""
    from decimal import Decimal
    import calendar

    # First invoice after subscription creation is already handled on checkout completion.
    # Avoid double extending period and double crediting.
    if invoice.get("billing_reason") == "subscription_create":
        return

    stripe_sub_id = invoice.get("subscription")
    if not stripe_sub_id:
        return

    try:
        sub = Subscription.objects.select_related("plan", "organization").get(
            stripe_subscription_id=stripe_sub_id
        )
    except Subscription.DoesNotExist:
        return

    now = tz.now()
    base = sub.end_date if sub.end_date and sub.end_date > now else now
    next_month = base.month + 1 if base.month < 12 else 1
    next_year = base.year if base.month < 12 else base.year + 1
    day = min(base.day, calendar.monthrange(next_year, next_month)[1])
    sub.end_date = base.replace(year=next_year, month=next_month, day=day)
    sub.status = "active"
    sub.renewed_at = now
    sub.save(update_fields=["end_date", "status", "renewed_at", "updated_at"])

    credits_usd = sub.get_effective_credits_limit_usd()
    if credits_usd:
        currency = Currency.objects.filter(name="Compute Unit").first()
        if currency:
            compute_units = Decimal(credits_usd) * Decimal(currency.one_usd_is)
            wallet = OrganizationWallet.objects.filter(organization=sub.organization).first()
            if wallet:
                wallet.recharge(compute_units)


def _handle_subscription_cancelled(stripe_sub):
    stripe_sub_id = stripe_sub.get("id")
    Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).update(
        status="cancelled", updated_at=tz.now()
    )


def _handle_subscription_updated(stripe_sub):
    stripe_sub_id = stripe_sub.get("id")
    if not stripe_sub_id:
        return

    current_period_end = stripe_sub.get("current_period_end")
    end_date = None
    if current_period_end:
        end_date = datetime.fromtimestamp(current_period_end, tz=timezone.utc)

    Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).update(
        status="active",
        end_date=end_date,
        updated_at=tz.now(),
    )


def _handle_payment_failed(invoice):
    stripe_sub_id = invoice.get("subscription")
    if stripe_sub_id:
        Subscription.objects.filter(stripe_subscription_id=stripe_sub_id).update(
            status="pending_payment", updated_at=tz.now()
        )


def _get_stripe_subscription_state(subscription):
    if (
        subscription.payment_method != "stripe"
        or not subscription.stripe_subscription_id
    ):
        return {
            "cancel_at_period_end": False,
            "cancel_at": None,
            "stripe_status": None,
        }

    try:
        stripe_sub = stripe.Subscription.retrieve(subscription.stripe_subscription_id)
    except stripe.StripeError:
        return {
            "cancel_at_period_end": False,
            "cancel_at": None,
            "stripe_status": None,
        }

    cancel_at_ts = stripe_sub.get("cancel_at")
    cancel_at = None
    if cancel_at_ts:
        cancel_at = datetime.fromtimestamp(cancel_at_ts, tz=timezone.utc).isoformat()

    return {
        "cancel_at_period_end": bool(stripe_sub.get("cancel_at_period_end")),
        "cancel_at": cancel_at,
        "stripe_status": stripe_sub.get("status"),
    }
