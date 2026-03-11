from django.core.management.base import BaseCommand, CommandError

from api.rag.managers import chroma_client
from api.rag.models import Collection


class Command(BaseCommand):
    help = "Backfill legacy (user, agent) vector collections into shared agent collections."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print actions without writing to Chroma.",
        )
        parser.add_argument(
            "--delete-legacy",
            action="store_true",
            help="Delete legacy Chroma collections after copy.",
        )

    def handle(self, *args, **options):
        if not chroma_client:
            raise CommandError("ChromaDB is not available.")

        dry_run = options["dry_run"]
        delete_legacy = options["delete_legacy"]

        legacy_collections = (
            Collection.objects.filter(user__isnull=False, agent__isnull=False)
            .select_related("agent", "user")
            .order_by("id")
        )

        if not legacy_collections.exists():
            self.stdout.write(self.style.SUCCESS("No legacy collections to backfill."))
            return

        copied_docs = 0
        copied_collections = 0

        for legacy in legacy_collections:
            target, _ = Collection.get_or_create_agent_collection(agent=legacy.agent)
            if legacy.slug == target.slug:
                continue

            source_collection = chroma_client.get_collection_or_none(legacy.slug)
            if source_collection is None:
                self.stdout.write(
                    self.style.WARNING(
                        f"Skipping legacy collection '{legacy.slug}' (not found in Chroma)."
                    )
                )
                continue

            payload = source_collection.get(include=["documents", "metadatas"])
            ids = payload.get("ids") or []
            documents = payload.get("documents") or []
            metadatas = payload.get("metadatas") or []
            if len(metadatas) != len(ids):
                metadatas = [{} for _ in ids]

            if not ids:
                self.stdout.write(
                    f"Legacy collection '{legacy.slug}' has no vectors. Nothing to copy."
                )
            else:
                copied_collections += 1
                copied_docs += len(ids)
                self.stdout.write(
                    f"Copy {len(ids)} vectors: '{legacy.slug}' -> '{target.slug}'"
                )
                if not dry_run:
                    chroma_client.bulk_upsert_chunks(
                        collection_name=target.slug,
                        documents=documents,
                        chunk_ids=ids,
                        metadatas=metadatas,
                    )

            if delete_legacy and not dry_run:
                chroma_client.delete_collection(legacy.slug)
                self.stdout.write(f"Deleted legacy collection '{legacy.slug}' from Chroma.")

        summary = (
            f"Backfill completed. Collections copied: {copied_collections}. "
            f"Vectors copied: {copied_docs}."
        )
        if dry_run:
            summary = "[DRY RUN] " + summary
        self.stdout.write(self.style.SUCCESS(summary))
