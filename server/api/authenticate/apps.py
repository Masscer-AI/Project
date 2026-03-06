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
            self._clear_feature_flag_cache()
        except (OperationalError, ProgrammingError):
            printer.red("Database not ready. Skipping feature-flag sync on startup.")

    @staticmethod
    def _clear_feature_flag_cache():
        """Clear all feature-flag related caches so stale data is never served after restart."""
        from django.core.cache import cache

        cache.delete("feature_flag_names")
        cache.delete_pattern("*ff_check_*")
        cache.delete_pattern("*ff_list_*")
        printer.green("Feature-flag cache cleared.")
