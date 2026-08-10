from django.core.management.base import BaseCommand

from api.whatsapp.template_sync import sync_default_whatsapp_templates


class Command(BaseCommand):
    help = (
        "Upsert WSTemplate rows from the in-code WhatsApp template registry. "
        "Creates missing templates and updates definition fields when they change. "
        "Does not modify organization subscriptions."
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

        created, updated, unchanged = sync_default_whatsapp_templates(dry_run=dry_run)

        if dry_run:
            if created:
                self.stdout.write(self.style.WARNING("Would create:"))
                for slug in created:
                    self.stdout.write(f"  - {slug}")
            if updated:
                self.stdout.write(self.style.WARNING("Would update:"))
                for slug in updated:
                    self.stdout.write(f"  - {slug}")
            if unchanged:
                self.stdout.write("Already up to date:")
                for slug in unchanged:
                    self.stdout.write(f"  - {slug}")
            return

        for slug in created:
            if verbosity >= 1:
                self.stdout.write(
                    self.style.SUCCESS(f'Created WhatsApp template: "{slug}"')
                )
        for slug in updated:
            if verbosity >= 1:
                self.stdout.write(
                    self.style.WARNING(f'Updated WhatsApp template: "{slug}"')
                )
        for slug in unchanged:
            if verbosity >= 2:
                self.stdout.write(f'Unchanged: "{slug}"')

        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. {len(created)} created, {len(updated)} updated, "
                    f"{len(unchanged)} unchanged."
                )
            )
