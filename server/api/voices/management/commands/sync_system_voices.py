from django.core.management.base import BaseCommand

from api.voices.seed import sync_system_voices


class Command(BaseCommand):
    help = (
        "Ensure all system voices (OpenAI + ElevenLabs) exist in the DB. "
        "Creates missing voices and updates name/slug/metadata when definitions change. "
        "Run after migrate or on deployment — same idea as sync_subscription_plans."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show what would be created/updated; do not modify the DB.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        verbosity = options.get("verbosity", 1)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes will be made."))

        created, updated, unchanged = sync_system_voices(dry_run=dry_run)

        if dry_run:
            if created:
                self.stdout.write(self.style.WARNING("Would create:"))
                for slug in created:
                    self.stdout.write(f"  - {slug}")
            if unchanged:
                self.stdout.write("Already exist:")
                for slug in unchanged:
                    self.stdout.write(f"  - {slug}")
            return

        for slug in created:
            if verbosity >= 1:
                self.stdout.write(self.style.SUCCESS(f'Created system voice: "{slug}"'))
        for slug in updated:
            if verbosity >= 1:
                self.stdout.write(self.style.WARNING(f'Updated system voice: "{slug}"'))
        for slug in unchanged:
            if verbosity >= 2:
                self.stdout.write(f'Unchanged: "{slug}"')

        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. {len(created)} created, {len(updated)} updated, {len(unchanged)} unchanged."
                )
            )
