from __future__ import annotations

SEED = (
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


def seed_pld_matrix() -> None:
    from api.compliance.models import PLDMatrix

    for slug, name, kind, points in SEED:
        PLDMatrix.objects.get_or_create(
            slug=slug,
            defaults={"name": name, "kind": kind, "points": points},
        )
