from django.apps import AppConfig
from api.utils.color_printer import printer
from django.db import OperationalError

DEFAULT_WINNING_RATE_NAME = "default"


class PaymentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.payments"

    def ready(self):

        from .models import WinningRates

        try:
            if WinningRates.objects.filter(name=DEFAULT_WINNING_RATE_NAME).exists():
                # printer.info("Default winning rates already exist")
                return

            WinningRates.objects.create(name=DEFAULT_WINNING_RATE_NAME)
            printer.success("Created default winning rates")
        except OperationalError as e:
            printer.error(f"Error in payments app ready method: {str(e)}")
