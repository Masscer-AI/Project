from django.apps import AppConfig
from django.db.utils import OperationalError, ProgrammingError
from api.utils.color_printer import printer


class ConsumptionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.consumption"

    def ready(self):
        self.startup_function()

    def startup_function(self):
        from .models import Currency
        

        try:
            if not Currency.objects.filter(name="Compute Unit").exists():
                Currency.objects.create(name="Compute Unit", one_usd_is=10000)
                printer.info("Compute Unit created")
            # else:
            #     printer.info("Compute Unit already exists")
        except OperationalError:
            printer.error("Database not ready, skipping Compute Unit creation")
        except ProgrammingError as e:
            printer.error(
                f"Error in consumption app ready method: {str(e)}, a ProgrammingError occurred."
            )

