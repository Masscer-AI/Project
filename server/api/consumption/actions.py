import logging

from .models import Consumption, Currency, OrganizationWallet, Wallet
from .wallet_ops import organization_wallet_use_balance
from api.ai_layers.models import LanguageModel
from api.payments.models import WinningRates
from decimal import Decimal
from api.notify.actions import notify_user

logger = logging.getLogger(__name__)


def notify_org_billing_denied(user_id, reason: str) -> None:
    """Notify the user when org-scoped billing blocks usage (subscription / balance)."""
    if reason == "subscription_expired":
        notify_user(user_id, "subscription_expired", {"message": "subscription-expired"})
    elif reason == "subscription_expired_with_purchased_locked":
        notify_user(
            user_id,
            "subscription_expired_with_purchased_locked",
            {"message": "subscription-expired-with-purchased-locked"},
        )
    elif reason in ("out_of_balance", "no_org_wallet"):
        notify_user(user_id, "out_of_balance", {"message": "out-of-compute-units"})
    elif reason == "no_subscription":
        notify_user(user_id, "no_subscription", {"message": "no-active-subscription"})
    elif reason == "billing_check_error":
        notify_user(user_id, "billing_check_error", {"message": "billing-check-failed"})


def _check_org_subscription(organization_id) -> tuple[bool, str]:
    """
    Verify the organization has an active subscription with credits remaining.
    Returns (allowed: bool, reason: str).
    """
    try:
        from api.payments.models import Subscription

        subscription = (
            Subscription.objects.filter(organization_id=organization_id)
            .order_by("-created_at")
            .first()
        )

        if subscription is None:
            return False, "no_subscription"

        if not subscription.is_active():
            try:
                org_wallet = OrganizationWallet.objects.get(organization_id=organization_id)
                if org_wallet.purchased_balance > 0:
                    return False, "subscription_expired_with_purchased_locked"
            except OrganizationWallet.DoesNotExist:
                pass
            return False, "subscription_expired"

        # Check org wallet balance (subscription + purchased)
        try:
            org_wallet = OrganizationWallet.objects.get(organization_id=organization_id)
        except OrganizationWallet.DoesNotExist:
            logger.warning(
                "OrganizationWallet missing for org_id=%s while subscription is active — denying",
                organization_id,
            )
            return False, "no_org_wallet"

        if org_wallet.total_balance <= 0:
            return False, "out_of_balance"

        return True, "ok"
    except Exception:
        logger.exception("Billing check failed for org_id=%s", organization_id)
        return False, "billing_check_error"


def register_consumption(
    user_id: int,
    amount: Decimal,
    is_for: str = "llm_interaction",
    organization_id=None,
):
    amount = Decimal(amount)
    amount = amount.quantize(Decimal("1.00000000"))

    # --- Organization context: check subscription + deduct from org wallet ---
    if organization_id is not None:
        allowed, reason = _check_org_subscription(organization_id)
        if not allowed:
            notify_org_billing_denied(user_id, reason)
            return False

        try:
            OrganizationWallet.objects.get(organization_id=organization_id)
        except OrganizationWallet.DoesNotExist:
            notify_org_billing_denied(user_id, "no_org_wallet")
            return False

        Consumption.objects.create(
            user_id=user_id, wallet=None, amount=amount, is_for=is_for
        )
        if not organization_wallet_use_balance(organization_id, amount):
            notify_org_billing_denied(user_id, "out_of_balance")
            return False
        return True

    # --- Per-user wallet (no org billing context) ---
    wallet, created = Wallet.objects.get_or_create(
        user_id=user_id, unit=Currency.objects.get(name="Compute Unit")
    )
    if created:
        wallet.balance = 5000
        wallet.save()
    Consumption.objects.create(
        user_id=user_id, wallet=wallet, amount=amount, is_for=is_for
    )

    if not wallet.use_balance(amount):
        notify_user(user_id, "out_of_balance", {"message": "out-of-compute-units"})
        return False
    return True


def split_price(price):
    usd_price, tokens = price.split("/")
    return float(usd_price.strip().replace(" USD", "").strip()), int(tokens.strip())


def calculate_consumption_llm_interaction(
    input_tokens: float, output_tokens: float, model_slug: str
):
    llm = LanguageModel.objects.get(slug=model_slug)
    pricing = llm.pricing
    input_price, input_tokens_relation = split_price(pricing["text"]["prompt"])
    output_price, output_tokens_relation = split_price(pricing["text"]["output"])

    usd_input_price = (input_price * input_tokens) / input_tokens_relation
    usd_output_price = (output_price * output_tokens) / output_tokens_relation

    return usd_input_price + usd_output_price


def apply_winning_rate_to_consumption(
    consumption_amount_usd: Decimal, type: str = "llm_interaction"
):

    winning_rate = 0.15
    default_winning_rate = WinningRates.objects.get(name="default")
    if type == "llm_interaction":
        winning_rate = default_winning_rate.llm_interaction_rate

    consumption_amount_usd = Decimal(consumption_amount_usd)
    return consumption_amount_usd * (1 + winning_rate)


def convert_usd_to_currency(amount_in_usd, currency_slug):
    currency = Currency.objects.get(slug=currency_slug)
    return Decimal(amount_in_usd) * Decimal(currency.one_usd_is)


IMAGE_MODEL_PRICING_USD = {
    "gpt-image-1.5": 0.10,  # $0.10 per image
    "gemini-2.5-flash-image": 0.10,  # $0.10 per image (1K resolution) — legacy
    "gemini-3.1-flash-lite-image": 0.034,  # $0.034 per 1K image (Nano Banana 2 Lite)
}

VIDEO_MODEL_PRICING_USD_PER_SECOND = {
    "veo-3.1-generate-001": 0.40,  # $0.40 per second
}


def calculate_consumption_image_generation(model_slug: str) -> float:
    price = IMAGE_MODEL_PRICING_USD.get(model_slug)
    if price is None:
        raise ValueError(f"No pricing configured for image model '{model_slug}'")
    return price


def register_image_generation(user_id, model_slug, organization_id=None):
    try:
        consumption_amount = calculate_consumption_image_generation(model_slug)

        winning_rates = WinningRates.objects.get(name="default")
        rate = winning_rates.image_generation_rate
        consumption_amount_with_rate = Decimal(consumption_amount) * (1 + rate)

        compute_units_amount = convert_usd_to_currency(consumption_amount_with_rate, "compute-unit")

        register_consumption(
            user_id,
            compute_units_amount,
            "image_generation",
            organization_id=organization_id,
        )
        return True
    except Exception as e:
        print(e, "exception trying to register image generation for user", user_id)
        return False


def register_video_generation(user_id, model_slug, duration_seconds, organization_id=None):
    try:
        price_per_second = VIDEO_MODEL_PRICING_USD_PER_SECOND.get(model_slug)
        if price_per_second is None:
            raise ValueError(f"No pricing configured for video model '{model_slug}'")

        consumption_amount = price_per_second * float(duration_seconds)

        winning_rates = WinningRates.objects.get(name="default")
        rate = winning_rates.image_generation_rate  # reuse same markup rate
        consumption_amount_with_rate = Decimal(consumption_amount) * (1 + rate)

        compute_units_amount = convert_usd_to_currency(consumption_amount_with_rate, "compute-unit")

        register_consumption(
            user_id,
            compute_units_amount,
            "video_generation",
            organization_id=organization_id,
        )
        return True
    except Exception as e:
        print(e, "exception trying to register video generation for user", user_id)
        return False


def register_llm_interaction(user_id, input_tokens, output_tokens, model_slug, organization_id=None):
    try:
        consumption_amount = calculate_consumption_llm_interaction(
            input_tokens, output_tokens, model_slug
        )

        complete_consumption = apply_winning_rate_to_consumption(consumption_amount)

        compute_units_amount = convert_usd_to_currency(
            complete_consumption, "compute-unit"
        )

        register_consumption(
            user_id,
            compute_units_amount,
            "llm_interaction",
            organization_id=organization_id,
        )
        return True
    except Exception as e:
        print(e, "exception trying to register llm interaction for user ", user_id)
        return False
