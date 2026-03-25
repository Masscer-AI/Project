from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone as tz
import datetime

from api.authenticate.models import Organization
from api.consumption.models import Currency, OrganizationWallet
from api.payments.models import Subscription, SubscriptionPlan


class Command(BaseCommand):
    help = (
        "Backfill subscriptions and wallets for organizations that don't have one. "
        "Safe to run multiple times — skips orgs that already have an active subscription/wallet."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without modifying the DB.",
        )
        parser.add_argument(
            "--plan",
            default="free_trial",
            help="Plan slug to assign to organizations missing a subscription (default: free_trial).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        plan_slug = options["plan"]
        verbosity = options.get("verbosity", 1)

        if dry_run:
            self.stdout.write(self.style.WARNING("Dry run: no changes will be made."))

        plan = SubscriptionPlan.objects.filter(slug=plan_slug).first()
        if plan is None:
            self.stdout.write(self.style.ERROR(
                f'Plan "{plan_slug}" not found. Run sync_subscription_plans first.'
            ))
            return

        currency = Currency.objects.filter(name="Compute Unit").first()
        if currency is None:
            self.stdout.write(self.style.ERROR(
                'Currency "Compute Unit" not found. Make sure it exists in the DB.'
            ))
            return

        credits_usd = plan.credits_limit_usd or Decimal("0")
        compute_units = credits_usd * Decimal(currency.one_usd_is)

        orgs = Organization.objects.all()
        total = orgs.count()

        subs_created = 0
        wallets_created = 0
        wallets_topped_up = 0
        skipped = 0

        for org in orgs:
            has_subscription = Subscription.objects.filter(organization=org).exists()
            wallet = OrganizationWallet.objects.filter(organization=org).first()
            wallet_needs_topup = wallet is not None and wallet.balance == 0 and compute_units > 0

            if has_subscription and wallet and not wallet_needs_topup:
                skipped += 1
                if verbosity >= 2:
                    self.stdout.write(f'  Skip "{org.name}" — already has subscription and wallet with balance.')
                continue

            if dry_run:
                if not has_subscription:
                    self.stdout.write(f'  Would create subscription ({plan_slug}) for "{org.name}"')
                    subs_created += 1
                if not wallet:
                    self.stdout.write(f'  Would create wallet ({compute_units} compute units) for "{org.name}"')
                    wallets_created += 1
                elif wallet_needs_topup:
                    self.stdout.write(f'  Would top up wallet to {compute_units} compute units for "{org.name}"')
                    wallets_topped_up += 1
                continue

            if not has_subscription:
                end_date = None
                if plan.duration_days:
                    end_date = tz.now() + datetime.timedelta(days=plan.duration_days)
                Subscription.objects.create(
                    organization=org,
                    plan=plan,
                    status="trial" if plan.slug == "free_trial" else "active",
                    payment_method="manual",
                    end_date=end_date,
                )
                subs_created += 1
                if verbosity >= 1:
                    self.stdout.write(self.style.SUCCESS(f'  Created subscription for "{org.name}"'))

            if not wallet:
                OrganizationWallet.objects.create(
                    organization=org,
                    balance=compute_units,
                    unit=currency,
                )
                wallets_created += 1
                if verbosity >= 1:
                    self.stdout.write(self.style.SUCCESS(f'  Created wallet for "{org.name}"'))
            elif wallet_needs_topup:
                wallet.balance = compute_units
                wallet.save(update_fields=["balance"])
                wallets_topped_up += 1
                if verbosity >= 1:
                    self.stdout.write(self.style.SUCCESS(f'  Topped up wallet for "{org.name}" → {compute_units} compute units'))

        if verbosity >= 1:
            self.stdout.write(self.style.SUCCESS(
                f"\nDone. {total} orgs checked — "
                f"{subs_created} subscriptions created, "
                f"{wallets_created} wallets created, "
                f"{wallets_topped_up} wallets topped up, "
                f"{skipped} skipped."
            ))
