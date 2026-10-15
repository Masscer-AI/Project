from __future__ import annotations

import os
import shutil
import tempfile
import zipfile

from django.utils.text import slugify

from api.compliance.invites import entity_display_name
from api.compliance.models import PLDEntity, PLDExpedientStatus
from api.compliance.packet.pdf import build_clarification_report_pdf

BUNDLE_READY = frozenset({PLDExpedientStatus.SIGNED, PLDExpedientStatus.DELIVERED})
_RELATIONSHIP_FOLDERS = {
    "cliente": "clientes",
    "proveedor": "proveedores",
    "ambos": "clientes-y-proveedores",
}


def _expedient(entity: PLDEntity):
    return entity.expedients.order_by("created_at").first()


def _copy(archive: zipfile.ZipFile, field, name: str) -> None:
    with field.open("rb") as source, archive.open(name, "w") as target:
        shutil.copyfileobj(source, target)


def _document_name(doc) -> str:
    filename = doc.original_filename or os.path.basename(doc.file.name)
    return f"{doc.slot_key.replace(':', '-')}-{filename}"


def entity_folder(entity: PLDEntity) -> str:
    name = slugify(entity_display_name(entity)) or "expediente"
    return f"{name}-{str(entity.id)[:8]}"


def entity_bundle_ready(entity: PLDEntity) -> bool:
    exp = _expedient(entity)
    return bool(exp and exp.status in BUNDLE_READY)


def organization_bundle_ready(organization) -> bool:
    own = PLDEntity.objects.filter(
        organization=organization, relationship__isnull=True
    ).first()
    return bool(own and entity_bundle_ready(own))


def _write_entity(archive: zipfile.ZipFile, entity: PLDEntity, prefix: str) -> None:
    exp = _expedient(entity)
    for doc in exp.documents.all():
        if doc.file:
            _copy(archive, doc.file, f"{prefix}documentos/{_document_name(doc)}")
    if exp.signed_packet:
        _copy(archive, exp.signed_packet, f"{prefix}expediente-firmado.pdf")
    elif exp.packet_file:
        _copy(archive, exp.packet_file, f"{prefix}expediente.pdf")
    if exp.signed_packet_xml:
        _copy(archive, exp.signed_packet_xml, f"{prefix}expediente-firmado.xml")
    report = build_clarification_report_pdf(entity)
    if report:
        archive.writestr(f"{prefix}reporte-aclaraciones.pdf", report)


def build_entity_bundle(entity: PLDEntity):
    handle = tempfile.TemporaryFile()
    with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        _write_entity(archive, entity, "")
    handle.seek(0)
    return handle


def build_organization_bundle(organization):
    entities = PLDEntity.objects.filter(organization=organization).prefetch_related(
        "expedients__documents"
    )
    handle = tempfile.TemporaryFile()
    with zipfile.ZipFile(handle, "w", zipfile.ZIP_DEFLATED) as archive:
        for entity in entities:
            if not entity_bundle_ready(entity):
                continue
            group = _RELATIONSHIP_FOLDERS.get(entity.relationship, "expediente-propio")
            _write_entity(archive, entity, f"{group}/{entity_folder(entity)}/")
    handle.seek(0)
    return handle
