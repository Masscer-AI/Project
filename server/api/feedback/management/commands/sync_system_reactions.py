from django.core.management.base import BaseCommand

from api.feedback.seed import sync_system_reactions


class Command(BaseCommand):
    help = (
        "Ensure system reaction templates exist. "
        "Only seeds when no system reactions are present."
    )

    def handle(self, *args, **options):
        created = sync_system_reactions()
        if created:
            self.stdout.write(
                self.style.SUCCESS(f"Created {created} system reaction(s).")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("System reactions already exist.")
            )
