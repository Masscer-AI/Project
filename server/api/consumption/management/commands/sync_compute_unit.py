from django.core.management.base import BaseCommand

from api.consumption.models import Currency


class Command(BaseCommand):
    help = (
        "Ensure the Compute Unit currency exists "
        "(1 USD = 10,000 compute units)."
    )

    def handle(self, *args, **options):
        currency, created = Currency.objects.get_or_create(
            name="Compute Unit",
            defaults={"one_usd_is": 10000},
        )
        if created:
            self.stdout.write(self.style.SUCCESS("Compute Unit currency created."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'Compute Unit already exists (1 USD = {currency.one_usd_is}).'
                )
            )
