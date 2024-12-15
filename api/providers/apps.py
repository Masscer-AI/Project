from django.apps import AppConfig
from django.db.utils import OperationalError
from api.utils.color_printer import printer
from dotenv import load_dotenv
import os

load_dotenv()


class ProvidersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.providers"

    def ready(self):
        self.startup_function()

    def startup_function(self):
        from .models import AIProvider

        printer.blue(f"Running startup function for {self.name}")
        try:
            # Check if an AIProvider with name.lower() == "ollama" exists
            if not AIProvider.objects.filter(name__iexact="ollama").exists():
                # If it doesn't exist, create it
                AIProvider.objects.create(name="Ollama")
                printer.green("AIProvider 'Ollama' created.")

            # Check if an AIProvider with name.lower() == "openai" exists
            if not AIProvider.objects.filter(name__iexact="openai").exists():
                # If it doesn't exist, create it
                AIProvider.objects.create(name="OpenAI")
                printer.green("AIProvider 'OpenAI' created.")

            ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
            # Check if an AIProvider with name.lower() == "anthropic" exists
            if (
                not AIProvider.objects.filter(name__iexact="anthropic").exists()
                and ANTHROPIC_API_KEY
            ):
                # If it doesn't exist, create it
                AIProvider.objects.create(name="Anthropic")
                printer.green("AIProvider 'Anthropic' created.")

        except OperationalError:
            # This exception might occur during migrations or if the database is not ready
            printer.red("Database is not ready. Skipping AIProvider check.")
