from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


# Order matters: providers before language models; currency + plans before org subscriptions.
SYNC_STEPS = (
    "sync_feature_flags",
    "sync_ai_providers",
    "sync_language_models",
    "sync_system_reactions",
    "sync_compute_unit",
    "sync_default_winning_rates",
    "sync_subscription_plans",
    "sync_system_voices",
    "sync_organization_subscriptions",
)

DRY_RUN_SUPPORTED = frozenset(
    {
        "sync_feature_flags",
        "sync_subscription_plans",
        "sync_system_voices",
        "sync_organization_subscriptions",
    }
)


class Command(BaseCommand):
    help = (
        "Run all idempotent system data syncs (feature flags, providers, models, "
        "reactions, currency, plans, voices, org subscriptions). "
        "Intended for deploy and local ./taskfile.sh run — not for migrate."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Forward --dry-run to child commands that support it.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbosity = options.get("verbosity", 1)

        for step in SYNC_STEPS:
            if verbosity >= 1:
                self.stdout.write(self.style.NOTICE(f"→ {step}"))
            try:
                kwargs = {"verbosity": verbosity}
                if dry_run and step in DRY_RUN_SUPPORTED:
                    kwargs["dry_run"] = True
                call_command(step, **kwargs)
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"{step} failed: {exc}"))
                raise CommandError(
                    f"sync_system_data aborted at '{step}'. "
                    f"Fix the error and re-run."
                ) from exc

        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"sync_system_data complete ({len(SYNC_STEPS)} steps)."
                )
            )
