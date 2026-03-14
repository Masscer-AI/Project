from django.db import migrations, models
from django.db.models import Q


def normalize_collection_ownership(apps, schema_editor):
    Collection = apps.get_model("rag", "Collection")
    Document = apps.get_model("rag", "Document")

    # Legacy shape was (user, agent). Move document ownership to personal collections
    # and normalize mixed collections to the new agent-only shared shape.
    mixed_collections = Collection.objects.filter(user__isnull=False, agent__isnull=False)
    for collection in mixed_collections.iterator():
        docs = Document.objects.filter(collection_id=collection.id)
        if docs.exists():
            personal, _ = Collection.objects.get_or_create(
                user_id=collection.user_id,
                agent_id=None,
                defaults={"name": collection.name},
            )
            docs.update(collection_id=personal.id)

        existing_agent_shared = (
            Collection.objects.filter(agent_id=collection.agent_id, user_id=None)
            .exclude(id=collection.id)
            .first()
        )
        if existing_agent_shared:
            collection.delete()
            continue

        collection.user_id = None
        collection.save(update_fields=["user"])

    # Safety cleanup: invalid owner-less rows are removed.
    Collection.objects.filter(user__isnull=True, agent__isnull=True).delete()

    # Deduplicate personal collections per user.
    personal_user_ids = (
        Collection.objects.filter(user__isnull=False, agent__isnull=True)
        .values_list("user_id", flat=True)
        .distinct()
    )
    for user_id in personal_user_ids:
        rows = list(
            Collection.objects.filter(user_id=user_id, agent_id=None).order_by("id")
        )
        keeper = rows[0]
        for extra in rows[1:]:
            Document.objects.filter(collection_id=extra.id).update(collection_id=keeper.id)
            extra.delete()

    # Deduplicate agent collections per agent.
    agent_ids = (
        Collection.objects.filter(agent__isnull=False, user__isnull=True)
        .values_list("agent_id", flat=True)
        .distinct()
    )
    for agent_id in agent_ids:
        rows = list(
            Collection.objects.filter(agent_id=agent_id, user_id=None).order_by("id")
        )
        keeper = rows[0]
        for extra in rows[1:]:
            Document.objects.filter(collection_id=extra.id).update(collection_id=keeper.id)
            extra.delete()


class Migration(migrations.Migration):
    # This migration performs data moves (updates/deletes) and then adds constraints.
    # On Postgres, running ALTER TABLE to add constraints in the same transaction as
    # large update/delete operations can fail with:
    #   "cannot ALTER TABLE ... because it has pending trigger events"
    # Running non-atomically ensures the data migration commits before constraints.
    atomic = False

    dependencies = [
        ("rag", "0008_document_total_tokens"),
    ]

    operations = [
        migrations.AlterField(
            model_name="collection",
            name="user",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.CASCADE,
                to="auth.user",
            ),
        ),
        migrations.RunPython(
            normalize_collection_ownership, migrations.RunPython.noop
        ),
        migrations.AddConstraint(
            model_name="collection",
            constraint=models.CheckConstraint(
                check=(
                    (Q(user__isnull=False) & Q(agent__isnull=True))
                    | (Q(user__isnull=True) & Q(agent__isnull=False))
                ),
                name="collection_exactly_one_owner",
            ),
        ),
        migrations.AddConstraint(
            model_name="collection",
            constraint=models.UniqueConstraint(
                condition=Q(user__isnull=False, agent__isnull=True),
                fields=("user",),
                name="collection_unique_personal_per_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="collection",
            constraint=models.UniqueConstraint(
                condition=Q(agent__isnull=False, user__isnull=True),
                fields=("agent",),
                name="collection_unique_shared_per_agent",
            ),
        ),
    ]
