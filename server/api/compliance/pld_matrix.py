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


SLUGS = tuple(slug for slug, _name, _kind, _points in SEED)
CUTOFF_ORDER = ("cutoff_yellow", "cutoff_orange", "cutoff_red")


def base_points() -> dict[str, float]:
    from api.compliance.models import PLDMatrix

    seed_pld_matrix()
    return {row.slug: float(row.points) for row in PLDMatrix.objects.all()}


def matrix_rows() -> list[dict]:
    from api.compliance.models import PLDMatrix

    seed_pld_matrix()
    order = {slug: index for index, slug in enumerate(SLUGS)}
    rows = sorted(PLDMatrix.objects.all(), key=lambda row: order.get(row.slug, len(order)))
    return [
        {"slug": row.slug, "name": row.name, "kind": row.kind, "points": row.points}
        for row in rows
    ]


def clean_points(raw) -> dict[str, float]:
    if not isinstance(raw, dict) or set(raw) != set(SLUGS):
        raise ValueError("points-incomplete")
    try:
        points = {slug: float(raw[slug]) for slug in SLUGS}
    except (TypeError, ValueError):
        raise ValueError("points-not-numbers")
    if any(value < 0 for value in points.values()):
        raise ValueError("points-negative")
    weights = sum(points[slug] for slug in SLUGS if slug.startswith("weight_"))
    if round(weights, 2) != 100:
        raise ValueError("weights-must-sum-100")
    cutoffs = [points[slug] for slug in CUTOFF_ORDER]
    if cutoffs != sorted(cutoffs) or len(set(cutoffs)) != len(cutoffs) or cutoffs[-1] > 100:
        raise ValueError("cutoffs-out-of-order")
    return points


def profile_payload(profile) -> dict:
    return {
        "id": str(profile.id),
        "name": profile.name,
        "is_default": profile.is_default,
        "points": profile.points,
        "entity_count": profile.entities.count(),
    }
