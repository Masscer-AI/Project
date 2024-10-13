from django.apps import AppConfig
from api.utils.color_printer import printer

class AiLayersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.ai_layers"

    def ready(self) -> None:
        import api.ai_layers.signals
        self.startup_function()

    def startup_function(self):
        from api.ai_layers.actions import check_models_for_providers
        # from .models import LanguageModel
        # from api.providers.models import AIProvider
        # from api.utils.ollama_functions import list_ollama_models
        # from api.utils.openai_functions import list_openai_models

        printer.blue(f"Running startup function for {self.name}")
        check_models_for_providers()
