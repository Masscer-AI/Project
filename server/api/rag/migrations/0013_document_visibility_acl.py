# Generated manually for document visibility ACL (personal / organization / roles)

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_document_ownership(apps, schema_editor):
    Document = apps.get_model("rag", "Document")
    Organization = apps.get_model("authenticate", "Organization")
    UserProfile = apps.get_model("authenticate", "UserProfile")

    owner_org_by_user = {
        org.owner_id: org
        for org in Organization.objects.exclude(owner_id__isnull=True).only("id", "owner_id")
    }
    profile_org_by_user = {
        p.user_id: p.organization_id
        for p in UserProfile.objects.exclude(organization_id__isnull=True).only(
            "user_id", "organization_id"
        )
    }

    for doc in Document.objects.select_related("collection").iterator():
        owner_id = None
        if getattr(doc, "created_by_id", None):
            owner_id = doc.created_by_id
        elif doc.collection_id and getattr(doc.collection, "user_id", None):
            owner_id = doc.collection.user_id

        updates = []
        if owner_id and not doc.created_by_id:
            doc.created_by_id = owner_id
            updates.append("created_by")

        org_id = None
        if owner_id:
            owned = owner_org_by_user.get(owner_id)
            if owned:
                org_id = owned.id
            else:
                org_id = profile_org_by_user.get(owner_id)

        if org_id:
            doc.visibility = "organization"
            doc.organization_id = org_id
            updates.extend(["visibility", "organization"])
        else:
            doc.visibility = "personal"
            doc.organization_id = None
            updates.extend(["visibility", "organization"])

        if updates:
            doc.save(update_fields=list(dict.fromkeys(updates)))


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("authenticate", "0026_userprofile__phone_numbers"),
        ("rag", "0012_document_drive_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="document",
            name="visibility",
            field=models.CharField(
                choices=[
                    ("personal", "Personal"),
                    ("organization", "Organization"),
                    ("roles", "Roles"),
                ],
                db_index=True,
                default="personal",
                help_text="Who can see this document in the knowledge base: me, organization, or selected roles.",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="organization",
            field=models.ForeignKey(
                blank=True,
                help_text="Organization scope when visibility is organization or roles.",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="rag_documents",
                to="authenticate.organization",
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                help_text="User who uploaded/created this document.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_rag_documents",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="document",
            name="allowed_roles",
            field=models.ManyToManyField(
                blank=True,
                help_text="When visibility is roles, users with any of those roles (or the org owner) can access.",
                related_name="rag_documents",
                to="authenticate.role",
            ),
        ),
        migrations.RunPython(backfill_document_ownership, noop_reverse),
    ]
