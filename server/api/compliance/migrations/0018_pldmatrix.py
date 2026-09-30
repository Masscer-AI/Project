from django.db import migrations, models


def seed_matrix(apps, schema_editor):
    PLDMatrix = apps.get_model("compliance", "PLDMatrix")
    rows = (
        ("weight_authenticity", "Autenticidad del alta", "weight", 5),
        ("weight_identity", "Identidad legal", "weight", 12),
        ("weight_controller", "Beneficiario controlador", "weight", 16),
        ("weight_representative", "Representante legal", "weight", 6),
        ("weight_activity", "Actividad economica", "weight", 10),
        ("weight_geography", "Riesgo geografico", "weight", 8),
        ("weight_transactional", "Perfil transaccional", "weight", 12),
        ("weight_integrity", "Integridad documental", "weight", 16),
        ("weight_screening", "Cruce de listas", "weight", 10),
        ("weight_conduct", "Conducta y senales", "weight", 5),
        ("adjust_pep", "PEP declarado", "adjustment", 5),
        ("adjust_vulnerable", "Actividad vulnerable", "adjustment", 8),
        ("adjust_third_party", "Pagos de terceros", "adjustment", 15),
        ("adjust_foreign", "Operaciones fuera de Mexico", "adjustment", 5),
        ("adjust_controller_missing", "Controlador incompleto", "adjustment", 15),
        ("adjust_mismatch", "Inconsistencia material", "adjustment", 20),
        ("cutoff_yellow", "Amarillo desde", "cutoff", 25),
        ("cutoff_orange", "Naranja desde", "cutoff", 45),
        ("cutoff_red", "Rojo desde", "cutoff", 65),
    )
    for slug, name, kind, points in rows:
        PLDMatrix.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "kind": kind, "points": points},
        )


class Migration(migrations.Migration):
    dependencies = [
        ("compliance", "0017_alter_pldexpedient_risk_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="PLDMatrix",
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
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=120)),
                (
                    "kind",
                    models.CharField(
                        choices=[
                            ("weight", "Weight"),
                            ("adjustment", "Adjustment"),
                            ("cutoff", "Cutoff"),
                        ],
                        max_length=16,
                    ),
                ),
                ("points", models.FloatField()),
            ],
            options={
                "verbose_name": "PLD matrix",
                "verbose_name_plural": "PLD matrix",
                "ordering": ["kind", "slug"],
            },
        ),
        migrations.RunPython(seed_matrix, migrations.RunPython.noop),
    ]
