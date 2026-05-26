import django.db.models.deletion
from django.db import migrations, models


def default_context_rules():
    return {"include_always": False, "include_for_tags": []}


def backfill_completion_assignments(apps, schema_editor):
    Completion = apps.get_model("finetuning", "Completion")
    CompletionAssignment = apps.get_model("finetuning", "CompletionAssignment")
    for completion in Completion.objects.filter(agent_id__isnull=False).iterator():
        CompletionAssignment.objects.get_or_create(
            completion_id=completion.id,
            agent_id=completion.agent_id,
        )


def backfill_training_generator_agents(apps, schema_editor):
    TrainingGenerator = apps.get_model("finetuning", "TrainingGenerator")
    for generator in TrainingGenerator.objects.filter(agent_id__isnull=False).iterator():
        generator.agents.add(generator.agent_id)


class Migration(migrations.Migration):

    dependencies = [
        ("ai_layers", "0024_alter_agent_model_provider"),
        ("finetuning", "0008_alter_traininggenerator_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="completion",
            name="context_rules",
            field=models.JSONField(default=default_context_rules),
        ),
        migrations.CreateModel(
            name="CompletionAssignment",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "agent",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="completion_assignments",
                        to="ai_layers.agent",
                    ),
                ),
                (
                    "completion",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assignments",
                        to="finetuning.completion",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="completionassignment",
            constraint=models.UniqueConstraint(
                fields=("completion", "agent"),
                name="completion_assignment_unique_completion_agent",
            ),
        ),
        migrations.AddIndex(
            model_name="completionassignment",
            index=models.Index(fields=["agent"], name="finetuning__agent_i_8f3c2a_idx"),
        ),
        migrations.AddIndex(
            model_name="completionassignment",
            index=models.Index(fields=["completion"], name="finetuning__complet_91a4b1_idx"),
        ),
        migrations.AddIndex(
            model_name="completion",
            index=models.Index(fields=["approved"], name="finetuning__approve_2d8e01_idx"),
        ),
        migrations.AddField(
            model_name="traininggenerator",
            name="agents",
            field=models.ManyToManyField(
                blank=True,
                related_name="training_generators",
                to="ai_layers.agent",
            ),
        ),
        migrations.RunPython(
            backfill_completion_assignments,
            migrations.RunPython.noop,
        ),
        migrations.RunPython(
            backfill_training_generator_agents,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name="completion",
            name="agent",
        ),
        migrations.RemoveField(
            model_name="traininggenerator",
            name="agent",
        ),
    ]
