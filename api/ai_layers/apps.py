from django.apps import AppConfig
from api.utils.color_printer import printer
from django.db.utils import OperationalError, ProgrammingError
import requests


class AiLayersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.ai_layers"

    def ready(self) -> None:
        import api.ai_layers.signals

        self.startup_function()

    def startup_function(self):
        from api.ai_layers.actions import check_models_for_providers

        try:
            # printer.blue(f"Running startup function for {self.name}")
            check_models_for_providers()
        except OperationalError:
            # This exception might occur during migrations or if the database is not ready
            printer.red("Database is not ready. Skipping AIProvider check.")
        except ProgrammingError as e:
            # This exception occurs when tables don't exist (migrations not run yet)
            printer.yellow(f"Database tables not ready yet: {str(e)}. Skipping AIProvider check.")
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            # Ollama is not available
            printer.yellow(f"Ollama is not available. Skipping AIProvider check.")
        except Exception as e:
            # Catch any other exceptions to prevent Django startup from failing
            printer.yellow(f"Error in AIProvider check: {str(e)}. Skipping.")
