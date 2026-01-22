from django.core.management.base import BaseCommand

from api.authenticate.feature_flags_registry import KNOWN_FEATURE_FLAGS
from api.authenticate.models import FeatureFlag


class Command(BaseCommand):
    help = (
        "Ensure all known feature flags exist in the DB. "
        "Creates any missing flags; existing ones are left unchanged. "
        "Run after migrate or on startup to keep flags in sync with the codebase."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list which flags would be created; do not modify the DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbosity = options.get("verbosity", 1)

        if dry_run:
            self.stdout.write(
                self.style.WARNING("Dry run: no changes will be made.")
            )

        created = []
        existing = []

        for name in KNOWN_FEATURE_FLAGS:
            if dry_run:
                exists = FeatureFlag.objects.filter(name=name).exists()
                if exists:
                    existing.append(name)
                else:
                    created.append(name)
                continue

            flag, was_created = FeatureFlag.objects.get_or_create(
                name=name,
                defaults={},
            )
            if was_created:
                created.append(name)
            else:
                existing.append(name)

        if dry_run:
            if created:
                self.stdout.write(
                    self.style.WARNING("Would create:")
                )
                for n in created:
                    self.stdout.write(f"  - {n}")
            if existing:
                self.stdout.write("Already exist:")
                for n in existing:
                    self.stdout.write(f"  - {n}")
            if not created and not existing:
                self.stdout.write("No flags in registry.")
            return

        for n in created:
            if verbosity >= 1:
                self.stdout.write(self.style.SUCCESS(f'Created feature flag: "{n}"'))
        for n in existing:
            if verbosity >= 2:
                self.stdout.write(f'Already exists: "{n}"')

        if verbosity >= 1 and created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. {len(created)} created, {len(existing)} already existed."
                )
            )
        elif verbosity >= 1 and not created:
            self.stdout.write(
                self.style.SUCCESS("All known feature flags already exist.")
            )
