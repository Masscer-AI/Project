from django.db import migrations, models
import django.db.models.deletion


def assign_default_language_model_list(apps, schema_editor):
    Organization = apps.get_model("authenticate", "Organization")
    LanguageModelList = apps.get_model("ai_layers", "LanguageModelList")
    default = LanguageModelList.objects.filter(slug="default").first()
    if not default:
        return
    Organization.objects.filter(language_model_list__isnull=True).update(
        language_model_list=default
    )


class Migration(migrations.Migration):

    dependencies = [
        ("authenticate", "0029_organization_pld_access_enabled"),
        ("ai_layers", "0036_languagemodellist"),
    ]

    operations = [
        migrations.AddField(
            model_name="organization",
            name="language_model_list",
            field=models.ForeignKey(
                blank=True,
                help_text="Which language model list this organization may use.",
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="organizations",
                to="ai_layers.languagemodellist",
            ),
        ),
        migrations.RunPython(
            assign_default_language_model_list, migrations.RunPython.noop
        ),
    ]
