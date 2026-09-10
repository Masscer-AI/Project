"""Versioned critical-rule catalog for the PLD risk gate (not the 100-point matrix)."""

from __future__ import annotations

RISK_GATE_VERSION = "2026.1-gates"

SEMAPHORE_RANK = {
    "green": 0,
    "yellow": 1,
    "orange": 2,
    "red": 3,
}

SAT_69_SLUGS = frozenset(
    {
        "sat_69_firmes",
        "sat_69_no_localizados",
        "sat_69_exigibles",
        "sat_69_sentencias",
        "sat_69_csd",
    }
)

INVITEE_SUMMARY = {
    "green": "Tu expediente sigue en revision interna.",
    "yellow": "Hace falta confirmar o completar algunos datos para continuar.",
    "orange": "Hace falta confirmar o completar algunos datos para continuar.",
    "red": "El expediente requiere revision adicional.",
}


def rank_semaphore(value: str) -> int:
    return SEMAPHORE_RANK.get(value, 0)


def max_semaphore(current: str, candidate: str) -> str:
    if rank_semaphore(candidate) > rank_semaphore(current):
        return candidate
    return current


def classify_hit(hit: dict) -> tuple[str, str]:
    """Return (screening_class_hint, fiscal_kind).

    screening_class_hint is possible|confirmed for this hit only.
    fiscal_kind is art_69, 69b_presunto, 69b_definitivo, 69b_bis, onu, or empty.
    """
    slug = str(hit.get("list_slug") or "").strip()
    situation = str(hit.get("situation") or hit.get("notes") or "").casefold()
    strength = str(hit.get("strength") or "weak")
    klass = "confirmed" if strength == "exact" else "possible"
    fiscal = ""
    if slug == "onu_csnu":
        fiscal = "onu"
    elif slug == "sat_69b_bis":
        fiscal = "69b_bis"
    elif slug == "sat_69b":
        if "desvirtu" in situation or "sentencia favorable" in situation:
            fiscal = "69b_desvirtuado"
        elif "presunt" in situation:
            fiscal = "69b_presunto"
        elif "definit" in situation:
            fiscal = "69b_definitivo"
        else:
            fiscal = "69b"
    elif slug in SAT_69_SLUGS:
        fiscal = "art_69"
    return klass, fiscal
