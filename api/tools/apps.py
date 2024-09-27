from django.apps import AppConfig


class ToolsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api.tools'
    def ready(self) -> None:
        import api.tools.signals