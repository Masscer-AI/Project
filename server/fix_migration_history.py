#!/usr/bin/env python
"""Repair the known integrations migration-history ordering issue."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "api.settings")

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.db import connection  # noqa: E402
from django.db.migrations.recorder import MigrationRecorder  # noqa: E402


DEPENDENCY = ("integrations", "0002_alter_integration_provider")
MISSING_MIGRATION = ("integrations", "0003_ensure_integration_table")


def main() -> None:
    recorder = MigrationRecorder(connection)
    applied = recorder.applied_migrations()

    if MISSING_MIGRATION in applied:
        print("Migration history is already consistent; no repair needed.")
        return

    if DEPENDENCY not in applied:
        print("Previous integrations migration is not applied; no repair needed.")
        return

    integration = apps.get_model("integrations", "Integration")
    table_name = integration._meta.db_table
    if table_name not in connection.introspection.table_names():
        print(
            f"Table {table_name!r} does not exist; leaving migration "
            "integrations.0003 for Django to apply."
        )
        return

    recorder.record_applied(*MISSING_MIGRATION)
    print(
        "Repaired migration history: marked "
        "integrations.0003_ensure_integration_table as applied."
    )


if __name__ == "__main__":
    main()
