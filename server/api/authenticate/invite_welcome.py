import re

from api.authenticate.phone_numbers import to_meta_whatsapp_digits
from api.whatsapp.models import WSNumber

_DIGITS_RE = re.compile(r"[^\d]")

WELCOME_TEMPLATE_ES = "bienvenido_a_presentacion_agente_es"
WELCOME_TEMPLATE_EN = "welcome_to_agent_presentation_en"


def welcome_template_id(language: str) -> str:
    if (language or "").lower().startswith("es"):
        return WELCOME_TEMPLATE_ES
    return WELCOME_TEMPLATE_EN


def normalize_welcome_language(value: str) -> str:
    if (value or "").lower().startswith("es"):
        return "es"
    return "en"


def normalize_welcome_phones(raw) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in raw or []:
        digits = to_meta_whatsapp_digits(_DIGITS_RE.sub("", str(item or "")))
        if not digits or digits in seen:
            continue
        seen.add(digits)
        out.append(digits)
    return out


def welcome_lines_for_org(organization, line_ids) -> list[WSNumber]:
    ids: list[int] = []
    seen: set[int] = set()
    for raw in line_ids or []:
        try:
            pk = int(raw)
        except (TypeError, ValueError):
            continue
        if pk in seen:
            continue
        seen.add(pk)
        ids.append(pk)
    if not ids:
        return []
    rows = list(
        WSNumber.objects.filter(organization=organization, pk__in=ids)
        .exclude(platform_id__isnull=True)
        .exclude(platform_id="")
        .select_related("agent")
    )
    by_id = {n.id: n for n in rows}
    if any(i not in by_id for i in ids):
        raise ValueError("WhatsApp line not found")
    return [by_id[i] for i in ids]
