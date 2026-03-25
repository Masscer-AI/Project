from .models import Consumption, Currency, OrganizationWallet, Wallet
from api.ai_layers.models import LanguageModel
from api.payments.models import WinningRates
from decimal import Decimal
from api.notify.actions import notify_user


def _check_org_subscription(organization_id) -> tuple[bool, str]:
    """
    Verify the organization has an active subscription with credits remaining.
    Returns (allowed: bool, reason: str).
    """
    try:
        from api.payments.models import Subscription
        from django.utils import timezone as tz

        subscription = (
            Subscription.objects.filter(organization_id=organization_id)
            .order_by("-created_at")
            .first()
        )

        if subscription is None:
            return False, "no_subscription"

        if not subscription.is_active():
            return False, "subscription_expired"

        # Check org wallet balance
        try:
            org_wallet = OrganizationWallet.objects.get(organization_id=organization_id)
        except OrganizationWallet.DoesNotExist:
            # Wallet missing — allow but log; shouldn't happen after signal runs
            return True, "ok"

        if org_wallet.balance <= 0:
            return False, "out_of_balance"

        return True, "ok"
    except Exception as e:
        print(e, "exception checking org subscription for org", organization_id)
        # Fail open to avoid blocking users on infrastructure errors
        return True, "ok"


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
            if reason == "subscription_expired":
                notify_user(user_id, "subscription_expired", {"message": "subscription-expired"})
            elif reason == "out_of_balance":
                notify_user(user_id, "out_of_balance", {"message": "out-of-compute-units"})
            elif reason == "no_subscription":
                notify_user(user_id, "no_subscription", {"message": "no-active-subscription"})
            return False

        try:
            org_wallet = OrganizationWallet.objects.get(organization_id=organization_id)
            Consumption.objects.create(
                user_id=user_id, wallet=None, amount=amount, is_for=is_for
            )
            if not org_wallet.use_balance(amount):
                notify_user(user_id, "out_of_balance", {"message": "out-of-compute-units"})
                return False
            return True
        except OrganizationWallet.DoesNotExist:
            pass  # Fall through to per-user wallet below

    # --- Per-user wallet (no org context or org wallet missing) ---
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
