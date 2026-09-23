from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("ai_layers", "0035_rename_rag_query_to_memory_search"),
    ]

    operations = [
        migrations.CreateModel(
            name="LanguageModelList",
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
                ("slug", models.CharField(max_length=100, unique=True)),
                ("name", models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name="LanguageModelListMembership",
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
                (
                    "list",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="memberships",
                        to="ai_layers.languagemodellist",
                    ),
                ),
                (
                    "language_model",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="list_memberships",
                        to="ai_layers.languagemodel",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="languagemodellistmembership",
            constraint=models.UniqueConstraint(
                fields=("list", "language_model"),
                name="uniq_languagemodellistmembership_list_model",
            ),
        ),
        migrations.AddField(
            model_name="languagemodel",
            name="lists",
            field=models.ManyToManyField(
                blank=True,
                related_name="language_models",
                through="ai_layers.LanguageModelListMembership",
                to="ai_layers.languagemodellist",
            ),
        ),
    ]
