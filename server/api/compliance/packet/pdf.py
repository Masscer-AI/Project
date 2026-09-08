from __future__ import annotations

from django.utils import timezone

import fitz

from api.compliance.invites import entity_display_name
from api.compliance.pld_document_slots import document_slots_for_entity

A4 = (595, 842)
MARGIN = 52
BODY_SIZE = 10.5
TITLE_SIZE = 14


def _addr(meta: dict) -> str:
    raw = meta.get("address")
    if not isinstance(raw, dict):
        return ""
    parts = [
        raw.get("street"),
        raw.get("exterior_number"),
        raw.get("interior_number"),
        raw.get("neighborhood"),
        raw.get("municipality") or raw.get("city"),
        raw.get("state"),
        raw.get("postal_code"),
        raw.get("country"),
    ]
    return ", ".join(str(part).strip() for part in parts if part and str(part).strip())


def _controllers(meta: dict) -> list[str]:
    rows = []
    raw = meta.get("controllers")
    if isinstance(raw, list):
        for item in raw:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            extra = []
            if item.get("rfc"):
                extra.append(f"RFC {item['rfc']}")
            if item.get("ownership_percentage"):
                extra.append(f"{item['ownership_percentage']}%")
            rows.append(name + (f" ({', '.join(extra)})" if extra else ""))
    single = meta.get("controller")
    if not rows and isinstance(single, dict) and single.get("name"):
        rows.append(str(single["name"]).strip())
    if meta.get("is_own_controller") is True and not rows:
        rows.append("La misma persona fisica (beneficiario controlador).")
    return rows


def _document_lines(entity) -> list[str]:
    exp = entity.expedients.order_by("created_at").first()
    uploaded = {}
    if exp:
        uploaded = {doc.slot_key: doc for doc in exp.documents.all()}
    lines = []
    for slot in document_slots_for_entity(entity):
        doc = uploaded.get(slot["slot_key"])
        if not doc:
            continue
        if str(doc.slot_key).startswith("clarify:"):
            continue
        filename = doc.original_filename or slot["document_kind"]
        lines.append(f"- {filename} ({slot['document_kind']})")
    return lines


def _paragraphs(entity) -> list[str]:
    meta = entity.metadata if isinstance(entity.metadata, dict) else {}
    org_name = entity.organization.name
    subject = entity_display_name(entity)
    today = timezone.localtime().strftime("%d/%m/%Y")
    person = (
        "persona moral"
        if entity.person_type == "persona_moral"
        else "persona fisica"
    )
    rfc = str(meta.get("rfc") or "").strip() or "no declarado"
    curp = str(meta.get("curp") or "").strip()
    activity = str(meta.get("economic_activity") or "").strip()
    address = _addr(meta)
    representative = meta.get("representative") if isinstance(meta, dict) else None
    rep_line = ""
    if isinstance(representative, dict):
        rep_name = " ".join(
            part.strip()
            for part in (
                representative.get("given_names"),
                representative.get("surnames")
                or " ".join(
                    p
                    for p in (
                        representative.get("paternal_surname"),
                        representative.get("maternal_surname"),
                    )
                    if p
                ),
            )
            if part and str(part).strip()
        )
        if rep_name:
            rep_line = f"Representante legal: {rep_name}."
            if representative.get("rfc"):
                rep_line += f" RFC {representative['rfc']}."

    blocks = [
        "EXPEDIENTE DE IDENTIFICACION (PLD / KYB)",
        f"Sujeto obligado: {org_name}",
        f"Contraparte: {subject} ({person})",
        f"Fecha: {today}",
        "",
        "Este documento resume los datos y documentos que la contraparte "
        "entrego para su expediente de identificacion. Al firmar, declara "
        "que la informacion es veridica y vigente, y que actuara de buena fe "
        "frente al sujeto obligado.",
        "",
        "DATOS DE IDENTIFICACION",
        f"RFC: {rfc}",
    ]
    if curp:
        blocks.append(f"CURP: {curp}")
    if activity:
        blocks.append(f"Actividad economica: {activity}")
    if address:
        blocks.append(f"Domicilio: {address}")
    if rep_line:
        blocks.append(rep_line)

    controllers = _controllers(meta)
    blocks.extend(["", "BENEFICIARIO(S) CONTROLADOR(ES)"])
    if controllers:
        blocks.extend(f"- {row}" for row in controllers)
    else:
        blocks.append("- No declarado en el formulario.")

    docs = _document_lines(entity)
    blocks.extend(["", "DOCUMENTOS INTEGRADOS AL EXPEDIENTE"])
    if docs:
        blocks.extend(docs)
    else:
        blocks.append("- Sin archivos listados.")

    from api.compliance.packet.signatory import resolve_signatories

    firmantes = resolve_signatories(entity)
    blocks.extend(["", "FIRMANTES"])
    if firmantes:
        labels = {
            "representative": "representante legal",
            "controller": "beneficiario controlador",
            "counterparty": "contraparte",
        }
        for row in firmantes:
            role = labels.get(row["role"], row["role"])
            blocks.append(f"- {row['name']} ({role}) <{row['email']}>")
    else:
        blocks.append("- Pendiente de definir.")

    blocks.extend(
        [
            "",
            "DECLARACION",
            "Manifiesto que los datos y copias entregadas corresponden a la "
            "contraparte y, en su caso, a su representante y beneficiarios "
            "controladores. Me comprometo a informar cambios relevantes. "
            "Esta firma no implica que se haya comunicado un resultado de "
            "listas o una clasificacion de riesgo.",
            "",
            "Firma electronica via Mifiel (constancia NOM-151).",
        ]
    )
    return blocks


def build_identification_packet_pdf(entity) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=A4[0], height=A4[1])
    y = MARGIN
    for index, para in enumerate(_paragraphs(entity)):
        size = TITLE_SIZE if index == 0 else BODY_SIZE
        if not para:
            y += 8
            continue
        written = False
        while not written:
            if y > A4[1] - MARGIN - 36:
                page = doc.new_page(width=A4[0], height=A4[1])
                y = MARGIN
            rect = fitz.Rect(MARGIN, y, A4[0] - MARGIN, A4[1] - MARGIN)
            unused = page.insert_textbox(rect, para, fontsize=size, fontname="helv")
            if unused < 0:
                if y <= MARGIN:
                    break
                page = doc.new_page(width=A4[0], height=A4[1])
                y = MARGIN
                continue
            y += rect.height - unused + 4
            written = True
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
