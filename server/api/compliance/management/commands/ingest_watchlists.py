from django.core.management.base import BaseCommand, CommandError

from api.compliance.watchlists.ingest import ingest_all_watchlists


class Command(BaseCommand):
    help = "Download and ingest all configured watchlists (ONU CSNU and SAT Art. 69 / 69-B / 69-B Bis)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Ingest even if the file SHA-256 matches the latest snapshot.",
        )

    def handle(self, *args, **options):
        try:
            payload = ingest_all_watchlists(force=options["force"])
        except Exception as exc:
            raise CommandError(str(exc)) from exc
        for result in payload["results"]:
            self.stdout.write(
                f"{result['list_slug']}: {result['status']} "
                f"sha256={result['file_sha256'][:12]} "
                f"records={result.get('record_count', 0)}"
            )
        for error in payload["errors"]:
            self.stderr.write(self.style.ERROR(f"{error['list_slug']}: {error['error']}"))
        if payload["errors"]:
            raise CommandError("One or more watchlists failed to ingest")
