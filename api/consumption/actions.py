from .models import Consumption, Currency, Wallet
from api.ai_layers.models import LanguageModel
from api.payments.models import WinningRates
from decimal import Decimal


def register_consumption(
    user_id: int, amount: Decimal, is_for: str = "llm_interaction"
):
    amount = Decimal(amount)
    amount = amount.quantize(Decimal("1.00000000"))
    wallet, created = Wallet.objects.get_or_create(
        user_id=user_id, unit=Currency.objects.get(name="Compute Unit")
    )
    if created:
        wallet.balance = 5000
        wallet.save()
    wallet.use_balance(amount)
    Consumption.objects.create(
        user_id=user_id, wallet=wallet, amount=amount, is_for=is_for
    )


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


def register_llm_interaction(user_id, input_tokens, output_tokens, model_slug):
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
        )
        return True
    except Exception as e:
        print(e, "exception trying to register llm interaction for user ", user_id)
        return False
