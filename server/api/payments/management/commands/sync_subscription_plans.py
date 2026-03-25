from django.core.management.base import BaseCommand

from api.payments.models import SubscriptionPlan


PLANS = [
    {
        "slug": "free_trial",
        "display_name": "Free Trial",
        "monthly_price_usd": 0,
        "credits_limit_usd": 20,   # $20 USD = 200,000 compute units at 10,000/USD
        "duration_days": 3,
        "is_configurable": False,
    },
    {
        "slug": "pay_as_you_go",
        "display_name": "Pay As You Go",
        "monthly_price_usd": 0,
        "credits_limit_usd": None,
        "duration_days": None,
        "is_configurable": True,
    },
    {
        "slug": "organization",
        "display_name": "Organization Plan",
        "monthly_price_usd": 225,
        "credits_limit_usd": None,
        "duration_days": None,
        "is_configurable": False,
    },
]


class Command(BaseCommand):
    help = (
        "Ensure all subscription plans exist in the DB. "
        "Creates any missing plans; existing ones are updated if their definition changed. "
        "Run after migrate or on deployment to keep plans in sync."
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

        created = []
        updated = []
        unchanged = []

        for plan_data in PLANS:
            slug = plan_data["slug"]

            if dry_run:
                exists = SubscriptionPlan.objects.filter(slug=slug).exists()
                (created if not exists else unchanged).append(slug)
                continue

            plan, was_created = SubscriptionPlan.objects.get_or_create(
                slug=slug,
                defaults={k: v for k, v in plan_data.items() if k != "slug"},
            )

            if was_created:
                created.append(slug)
                continue

            # Update fields that may have changed
            changed_fields = []
            for field, value in plan_data.items():
                if field == "slug":
                    continue
                if getattr(plan, field) != value:
                    setattr(plan, field, value)
                    changed_fields.append(field)

            if changed_fields:
                plan.save(update_fields=changed_fields)
                updated.append(slug)
            else:
                unchanged.append(slug)

        if dry_run:
            if created:
                self.stdout.write(self.style.WARNING("Would create:"))
                for s in created:
                    self.stdout.write(f"  - {s}")
            if unchanged:
                self.stdout.write("Already exist:")
                for s in unchanged:
                    self.stdout.write(f"  - {s}")
            return

        for s in created:
            if verbosity >= 1:
                self.stdout.write(self.style.SUCCESS(f'Created plan: "{s}"'))
        for s in updated:
            if verbosity >= 1:
                self.stdout.write(self.style.WARNING(f'Updated plan: "{s}"'))
        for s in unchanged:
            if verbosity >= 2:
                self.stdout.write(f'Unchanged: "{s}"')

        if verbosity >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Done. {len(created)} created, {len(updated)} updated, {len(unchanged)} unchanged."
                )
            )
