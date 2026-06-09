"""
Management command: reprovision_platform_assistants

Creates or updates the Masscer Assistant for every active organization.
"Active" means the organization has at least one UserProfile linked.

Usage:
    uv run python manage.py reprovision_platform_assistants
    uv run python manage.py reprovision_platform_assistants --dry-run
    uv run python manage.py reprovision_platform_assistants --org-id <uuid>
"""

from django.core.management.base import BaseCommand

from api.ai_layers.platform_assistant import provision_platform_assistant
from api.authenticate.models import Organization, UserProfile


class Command(BaseCommand):
    help = "Create or update the Masscer Assistant for all active organizations."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List the organizations that would be reprovisioned without making changes.",
        )
        parser.add_argument(
            "--org-id",
            type=str,
            default=None,
            help="Reprovision a single organization by UUID.",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        org_id: str | None = options["org_id"]

        if org_id:
            try:
                orgs = Organization.objects.filter(pk=org_id)
                if not orgs.exists():
                    self.stderr.write(self.style.ERROR(f"Organization {org_id} not found."))
                    return
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"Invalid org id: {exc}"))
                return
        else:
            active_org_ids = (
                UserProfile.objects.filter(organization__isnull=False)
                .values_list("organization_id", flat=True)
                .distinct()
            )
            orgs = Organization.objects.filter(pk__in=active_org_ids)

        total = orgs.count()
        self.stdout.write(
            f"{'[DRY RUN] ' if dry_run else ''}"
            f"Found {total} organization(s) to reprovision."
        )

        created_count = 0
        updated_count = 0
        error_count = 0

        for org in orgs.order_by("name"):
            if dry_run:
                self.stdout.write(f"  · {org.name} ({org.id})")
                continue
            try:
                _agent, was_created = provision_platform_assistant(org)
                if was_created:
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  [created] {org.name} ({org.id})")
                    )
                else:
                    updated_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f"  [updated] {org.name} ({org.id})")
                    )
            except Exception as exc:
                error_count += 1
                self.stderr.write(
                    self.style.ERROR(f"  [error]   {org.name} ({org.id}): {exc}")
                )

        if not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\nDone. created={created_count} updated={updated_count} errors={error_count}"
                )
            )
