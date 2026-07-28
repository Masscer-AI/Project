from django.core.management.base import BaseCommand

from api.payments.models import WinningRates

DEFAULT_WINNING_RATE_NAME = "default"


class Command(BaseCommand):
    help = 'Ensure the default WinningRates row (name="default") exists.'

    def handle(self, *args, **options):
        _, created = WinningRates.objects.get_or_create(name=DEFAULT_WINNING_RATE_NAME)
        if created:
            self.stdout.write(self.style.SUCCESS("Created default winning rates."))
        else:
            self.stdout.write(
                self.style.SUCCESS("Default winning rates already exist.")
            )
