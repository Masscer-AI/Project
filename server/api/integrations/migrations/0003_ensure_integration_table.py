"""
Repair migration for databases where integrations.0001_initial is recorded
in django_migrations but integrations_integration was never created.
"""

from __future__ import annotations

from django.db import connection, migrations


def ensure_integration_table(apps, schema_editor):
    Integration = apps.get_model("integrations", "Integration")
    table = Integration._meta.db_table
    existing = set(connection.introspection.table_names())
    if table in existing:
        return
    schema_editor.create_model(Integration)


class Migration(migrations.Migration):

    dependencies = [
        ("integrations", "0002_alter_integration_provider"),
    ]

    operations = [
        migrations.RunPython(ensure_integration_table, migrations.RunPython.noop),
    ]
