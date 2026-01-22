import sys

from django.apps import AppConfig
from django.core.management import call_command
from django.db.utils import OperationalError, ProgrammingError

from api.utils.color_printer import printer


class AuthenticateConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "api.authenticate"

    def ready(self):
        import api.authenticate.signals
        self._sync_feature_flags_on_startup()

    def _sync_feature_flags_on_startup(self):
        """Ensure all known feature flags exist after migrate. Skip if DB not ready or already running sync."""
        if "sync_feature_flags" in sys.argv:
            return
        try:
            call_command("sync_feature_flags", verbosity=1)
        except (OperationalError, ProgrammingError):
            printer.red("Database not ready. Skipping feature-flag sync on startup.")
