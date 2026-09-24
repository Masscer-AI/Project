from api.messaging.models import MessageAttachment
from api.rag.models import Document

KB_FROM_ATTACHMENT_METADATA_KEY = "knowledge_base_document_id"


def _doc_id(raw):
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def clear_kb_links_for_document(document_id) -> int:
    key = KB_FROM_ATTACHMENT_METADATA_KEY
    rows = MessageAttachment.objects.filter(metadata__has_key=key)
    cleared = 0
    for att in rows.iterator():
        metadata = att.metadata if isinstance(att.metadata, dict) else {}
        if _doc_id(metadata.get(key)) != int(document_id):
            continue
        metadata = dict(metadata)
        metadata.pop(key, None)
        att.metadata = metadata
        att.save(update_fields=["metadata"])
        cleared += 1
    return cleared


def clear_stale_kb_links(queryset) -> int:
    key = KB_FROM_ATTACHMENT_METADATA_KEY
    rows = [att for att in queryset if isinstance(att.metadata, dict) and key in att.metadata]
    wanted = {_doc_id(att.metadata.get(key)) for att in rows}
    wanted.discard(None)
    existing = set(Document.objects.filter(pk__in=wanted).values_list("pk", flat=True))
    cleared = 0
    for att in rows:
        doc_id = _doc_id(att.metadata.get(key))
        if doc_id in existing:
            continue
        metadata = dict(att.metadata)
        metadata.pop(key, None)
        att.metadata = metadata
        att.save(update_fields=["metadata"])
        cleared += 1
    return cleared
