from __future__ import annotations

import csv
import io
import re
from typing import Any

from api.compliance.models import WatchlistListSlug
from api.compliance.watchlists.normalize import build_search_document, fold_text

SAT_BLOB = (
    "https://wu1agsprosta001.blob.core.windows.net/agsc-publicaciones/"
    "Datos_abiertos"
)

SAT_SOURCES: dict[str, str] = {
    WatchlistListSlug.SAT_69B: (
        f"{SAT_BLOB}/Documents_AGAFF/Listado_completo_69-B.csv"
    ),
    WatchlistListSlug.SAT_69B_BIS: (
        f"{SAT_BLOB}/Documents_AGGC/Listado_69_B_Bis_Completo.csv"
    ),
    WatchlistListSlug.SAT_69_FIRMES: f"{SAT_BLOB}/Documents_AGR/Firmes.csv",
    WatchlistListSlug.SAT_69_NO_LOCALIZADOS: (
        f"{SAT_BLOB}/Documents_AGR/No_localizados.csv"
    ),
    WatchlistListSlug.SAT_69_EXIGIBLES: f"{SAT_BLOB}/Documents_AGR/Exigibles.csv",
    WatchlistListSlug.SAT_69_SENTENCIAS: f"{SAT_BLOB}/Documents_AGR/Sentencias.csv",
    WatchlistListSlug.SAT_69_CSD: f"{SAT_BLOB}/Documents_AGR/CSDsinefectos.csv",
}

_UPDATED_RE = re.compile(r"actualizada al\s+([^;,\n\r]+)", re.IGNORECASE)
_DATE_RE = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")

_NAME_HEADERS = {
    "nombre del contribuyente",
    "razon social",
    "nombre o razon social",
    "nombre",
}
_SITUATION_HEADERS = {
    "situacion del contribuyente",
    "supuesto",
    "supuesto de cancelacion csd",
}
_DATE_HEADERS = (
    "fecha de primera publicacion",
    "fechas de primera publicacion",
    "fecha de publicacion",
    "publicacion pagina sat presuntos",
    "publicacion pagina sat definitivos",
    "publicacion pagina sat definitivo",
    "fecha de cancelacion csd",
)


def decode_sat_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            text = data.decode(encoding)
        except UnicodeDecodeError:
            continue
        sample = text[:8000]
        if "RFC" in sample or "rfc" in sample.lower():
            return text
    return data.decode("cp1252", errors="replace")


def _header_key(value: str) -> str:
    return fold_text(value).replace(".", "")


def _cell(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def _first_date(*values: str) -> str:
    for value in values:
        match = _DATE_RE.search(value or "")
        if match:
            return match.group(0)
    return ""


def _record_type(rfc: str, tipo_persona: str) -> str:
    tipo = fold_text(tipo_persona)
    if tipo in {"f", "fisica", "persona fisica"}:
        return "individual"
    if tipo in {"m", "moral", "persona moral"}:
        return "entity"
    return "entity" if len(rfc) == 12 else "individual"


def _normalize_rfc(value: str) -> str:
    return "".join(str(value).split()).upper()


def parse_sat_csv(csv_bytes: bytes) -> dict[str, Any]:
    text = decode_sat_bytes(csv_bytes)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    header_idx = None
    date_generated = ""
    for idx, row in enumerate(rows[:8]):
        joined = " ".join(row)
        if not date_generated:
            match = _UPDATED_RE.search(joined)
            if match:
                date_generated = match.group(1).strip()
        keys = [_header_key(cell) for cell in row]
        if "rfc" in keys:
            header_idx = idx
            break
    if header_idx is None:
        raise ValueError("SAT CSV is missing an RFC header row")

    headers = [_header_key(cell) for cell in rows[header_idx]]
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw_row in rows[header_idx + 1 :]:
        if not any(cell.strip() for cell in raw_row):
            continue
        mapped = {
            headers[i]: (raw_row[i].strip() if i < len(raw_row) else "")
            for i in range(len(headers))
            if headers[i]
        }
        rfc = _normalize_rfc(_cell(mapped, "rfc"))
        if not rfc or rfc == "RFC":
            continue
        if rfc in seen:
            continue
        seen.add(rfc)
        name = _cell(mapped, *_NAME_HEADERS)
        situation = _cell(mapped, *_SITUATION_HEADERS)
        tipo = _cell(mapped, "tipo persona")
        listed_on = _first_date(*(_cell(mapped, key) for key in _DATE_HEADERS))
        estado = _cell(mapped, "entidad federativa")
        record_type = _record_type(rfc, tipo)
        names = [name] if name else []
        search_document = build_search_document(
            [
                rfc,
                name,
                situation,
                tipo,
                listed_on,
                estado,
                *mapped.values(),
            ]
        )
        records.append(
            {
                "record_type": record_type,
                "reference_number": rfc[:64],
                "data_id": rfc[:32],
                "primary_name": name[:512],
                "listed_on": listed_on[:32],
                "names": names,
                "dates_of_birth": [],
                "document_numbers": [rfc],
                "nationalities": ["MX"] if not estado else [estado],
                "search_document": search_document,
                "raw": mapped,
            }
        )
    return {"date_generated": date_generated, "records": records}
