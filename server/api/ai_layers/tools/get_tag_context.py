"""
Tool: get_tag_context

Returns other conversations that share a given tag id: by default only those
for the same user (owned + WhatsApp linked via WSContact.user); when the actor
has the conversations-dashboard feature, organization-wide threads.
"""

from __future__ import annotations

import logging
from datetime import datetime

from django.db.models import Count, DateTimeField, Q
from django.db.models.functions import Coalesce
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from api.messaging.conversation_access import user_accessible_conversations_q
from api.messaging.models import Conversation, Tag

logger = logging.getLogger(__name__)

MAX_CONVERSATIONS = 30
MAX_TAG_KIND = 30

TagContextInclude = Literal[
    "conversations",
    "knowledge_base_documents",
    "gallery",
]
DEFAULT_INCLUDES: tuple[TagContextInclude, ...] = (
    "conversations",
    "knowledge_base_documents",
    "gallery",
)


class GetTagContextParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_id: int = Field(
        ge=1,
        description=(
            "Numeric primary key of the tag (integer), e.g. 12 — NOT the tag title text. "
            "Use the tag_id shown next to current conversation tags or returned by query_organization_tags."
        ),
    )
    includes: list[TagContextInclude] | None = Field(
        default=None,
        description=(
            "Which kinds of tagged knowledge to return: conversations, "
            "knowledge_base_documents, gallery. Omit to include all three."
        ),
    )


class TagContextConversationItem(BaseModel):
    conversation_id: str = Field(description="UUID of the conversation")
    title: str = Field(default="", description="Conversation title if set")
    summary: str = Field(default="", description="Stored summary, may be empty")
    n_messages: int = Field(ge=0, description="Number of messages in the thread")
    date: str = Field(
        default="",
        description="ISO-8601 timestamp: last_message_at if set, otherwise updated_at",
    )


class TagContextDocumentItem(BaseModel):
    id: int
    name: str = ""
    brief: str = ""
    belongs_to: dict = Field(default_factory=dict)


class TagContextGalleryItem(BaseModel):
    attachment_id: str
    kind: str = ""
    name: str | None = None
    belongs_to: dict = Field(default_factory=dict)


class GetTagContextResult(BaseModel):
    conversations: list[TagContextConversationItem] = Field(default_factory=list)
    documents: list[TagContextDocumentItem] = Field(default_factory=list)
    gallery: list[TagContextGalleryItem] = Field(default_factory=list)
    message: str = Field(default="")


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return ""
    if hasattr(dt, "isoformat"):
        return dt.isoformat()
    return str(dt)


def _rows_to_items(qs) -> list[TagContextConversationItem]:
    items: list[TagContextConversationItem] = []
    for conv in qs:
        dt = getattr(conv, "sort_date", None) or conv.updated_at
        items.append(
            TagContextConversationItem(
                conversation_id=str(conv.id),
                title=(conv.title or "").strip(),
                summary=(conv.summary or "").strip(),
                n_messages=int(getattr(conv, "n_messages", 0) or 0),
                date=_iso(dt),
            )
        )
    return items


def _annotated_tag_qs(
    *,
    base,
    tag_id: int,
    current_conversation_id: str,
):
    tag_match = Q(tags__contains=[tag_id]) | Q(tags__contains=[str(tag_id)])
    return (
        base.filter(tag_match)
        .exclude(status="deleted")
        .exclude(id=current_conversation_id)
        .annotate(n_messages=Count("messages"))
        .annotate(
            sort_date=Coalesce(
                "last_message_at",
                "updated_at",
                output_field=DateTimeField(),
            )
        )
        .order_by("-sort_date")[:MAX_CONVERSATIONS]
    )


def _normalize_includes(includes: list[str] | None) -> set[str]:
    if not includes:
        return set(DEFAULT_INCLUDES)
    allowed = set(DEFAULT_INCLUDES)
    chosen = {str(x) for x in includes if str(x) in allowed}
    return chosen or set(DEFAULT_INCLUDES)


def _tagged_documents(*, user, tag_id: int) -> list[TagContextDocumentItem]:
    from api.messaging.organization_tags import tag_ids_match_q
    from api.rag.access import document_belongs_to_payload, documents_accessible_q
    from api.rag.models import Document

    qs = (
        Document.objects.filter(documents_accessible_q(user))
        .filter(tag_ids_match_q("tag_ids", [tag_id]))
        .select_related("organization", "created_by", "collection")
        .prefetch_related("allowed_roles")
        .distinct()
        .order_by("-created_at")[:MAX_TAG_KIND]
    )
    return [
        TagContextDocumentItem(
            id=doc.id,
            name=doc.name or "",
            brief=(doc.brief or "").strip(),
            belongs_to=document_belongs_to_payload(doc, user),
        )
        for doc in qs
    ]


def _tagged_gallery(
    *,
    user,
    tag_id: int,
    skip_document_ids: set[int],
) -> list[TagContextGalleryItem]:
    from api.messaging.attachment_access import (
        attachment_belongs_to_payload,
        attachments_visible_q,
    )
    from api.messaging.models import MessageAttachment
    from api.messaging.organization_tags import tag_ids_match_q

    qs = (
        MessageAttachment.objects.filter(
            attachments_visible_q(user=user),
        )
        .filter(tag_ids_match_q("tag_ids", [tag_id]))
        .select_related("rag_document", "organization", "user")
        .prefetch_related("allowed_roles")
        .distinct()
        .order_by("-created_at")[: MAX_TAG_KIND + 10]
    )
    items: list[TagContextGalleryItem] = []
    for att in qs:
        if (
            getattr(att, "kind", "") == "rag_document"
            and att.rag_document_id
            and int(att.rag_document_id) in skip_document_ids
        ):
            continue
        name = None
        if att.kind == "rag_document":
            doc = getattr(att, "rag_document", None)
            name = getattr(doc, "name", None)
        elif att.kind == "website":
            name = att.url
        elif att.file and getattr(att.file, "name", None):
            name = att.file.name.split("/")[-1]
        items.append(
            TagContextGalleryItem(
                attachment_id=str(att.id),
                kind=getattr(att, "kind", "") or "file",
                name=name,
                belongs_to=attachment_belongs_to_payload(att, user),
            )
        )
        if len(items) >= MAX_TAG_KIND:
            break
    return items


def _compose_message(
    *,
    tag,
    tag_id: int,
    includes: set[str],
    conversations: list,
    documents: list,
    gallery: list,
    conversation_scope: str,
) -> str:
    parts: list[str] = []
    if "conversations" in includes:
        if conversation_scope == "org":
            parts.append(
                f"{len(conversations)} other conversation(s) across the organization"
            )
        else:
            parts.append(f"{len(conversations)} other conversation(s) for this user")
    if "knowledge_base_documents" in includes:
        parts.append(f"{len(documents)} knowledge-base document(s)")
    if "gallery" in includes:
        parts.append(f"{len(gallery)} gallery/attachment item(s)")
    joined = "; ".join(parts) if parts else "no kinds requested"
    return f"Found {joined} with tag {tag_id!r} ({tag.title!r})."


def _get_tag_context_impl(
    *,
    tag_id: int,
    user_id: int,
    organization_id: int,
    current_conversation_id: str,
    has_organization_conversations_access: bool = False,
    includes: list[str] | None = None,
) -> GetTagContextResult:
    from django.contrib.auth.models import User

    chosen = _normalize_includes(includes)
    tag = (
        Tag.objects.filter(
            id=tag_id,
            organization_id=organization_id,
            enabled=True,
        )
        .only("id", "title")
        .first()
    )
    if not tag:
        return GetTagContextResult(
            message="Tag not found, not in this organization, or disabled.",
        )

    conversations: list[TagContextConversationItem] = []
    if "conversations" in chosen:
        base = Conversation.objects.filter(
            user_accessible_conversations_q(
                user_id=user_id,
                organization_id=organization_id,
                has_organization_conversations_access=has_organization_conversations_access,
            )
        )
        qs = _annotated_tag_qs(
            base=base,
            tag_id=tag_id,
            current_conversation_id=current_conversation_id,
        )
        conversations = _rows_to_items(qs)

    documents: list[TagContextDocumentItem] = []
    gallery: list[TagContextGalleryItem] = []
    user = User.objects.filter(pk=int(user_id)).first()
    if user is not None:
        if "knowledge_base_documents" in chosen:
            documents = _tagged_documents(user=user, tag_id=tag_id)
        if "gallery" in chosen:
            skip = {d.id for d in documents}
            gallery = _tagged_gallery(user=user, tag_id=tag_id, skip_document_ids=skip)

    scope = "org" if has_organization_conversations_access else "user"
    logger.info(
        "get_tag_context: user=%s tag_id=%s org=%s current=%s scope=%s conv=%s docs=%s gallery=%s",
        user_id,
        tag_id,
        organization_id,
        current_conversation_id,
        scope,
        len(conversations),
        len(documents),
        len(gallery),
    )
    return GetTagContextResult(
        conversations=conversations,
        documents=documents,
        gallery=gallery,
        message=_compose_message(
            tag=tag,
            tag_id=tag_id,
            includes=chosen,
            conversations=conversations,
            documents=documents,
            gallery=gallery,
            conversation_scope=scope,
        ),
    )


def _get_tag_context_organization_impl(
    *,
    tag_id: int,
    organization_id,
    current_conversation_id: str,
    includes: list[str] | None = None,
) -> GetTagContextResult:
    """All org threads with a tag (same visibility as dashboard scope=org)."""
    from api.messaging.views import organization_conversations_q

    chosen = _normalize_includes(includes)
    tag = (
        Tag.objects.filter(
            id=tag_id,
            organization_id=organization_id,
            enabled=True,
        )
        .only("id", "title")
        .first()
    )
    if not tag:
        return GetTagContextResult(
            message="Tag not found, not in this organization, or disabled.",
        )

    conversations: list[TagContextConversationItem] = []
    if "conversations" in chosen:
        qs = _annotated_tag_qs(
            base=Conversation.objects.filter(organization_conversations_q(organization_id)),
            tag_id=tag_id,
            current_conversation_id=current_conversation_id,
        )
        conversations = _rows_to_items(qs)

    return GetTagContextResult(
        conversations=conversations,
        message=_compose_message(
            tag=tag,
            tag_id=tag_id,
            includes=chosen,
            conversations=conversations,
            documents=[],
            gallery=[],
            conversation_scope="org",
        ),
    )


def get_tool(
    conversation_id: str | None = None,
    organization_id: int | None = None,
    user_id: int | None = None,
    has_organization_conversations_access: bool = False,
    is_whatsapp_visitor: bool = False,
    **kwargs,
) -> dict:
    if not conversation_id or organization_id is None:
        raise ValueError(
            "get_tag_context requires conversation_id and organization_id in context"
        )
    cid = str(conversation_id)

    if is_whatsapp_visitor:
        def get_tag_context(
            tag_id: int,
            includes: list[TagContextInclude] | None = None,
        ) -> GetTagContextResult:
            return _get_tag_context_organization_impl(
                tag_id=tag_id,
                organization_id=organization_id,
                current_conversation_id=cid,
                includes=includes,
            )

        return {
            "name": "get_tag_context",
            "description": (
                "Fetch knowledge for ONE tag: pass tag_id as an INTEGER. "
                "Optional includes: conversations, knowledge_base_documents, gallery "
                "(default all; this WhatsApp visitor path returns conversations only). "
                "Call before reusing a topic when a tag applies."
            ),
            "parameters": GetTagContextParams,
            "function": get_tag_context,
        }

    if user_id is None or not isinstance(user_id, int):
        raise ValueError("get_tag_context requires a logged-in user_id in context")

    uid = int(user_id)
    wide = bool(has_organization_conversations_access)

    def get_tag_context(
        tag_id: int,
        includes: list[TagContextInclude] | None = None,
    ) -> GetTagContextResult:
        return _get_tag_context_impl(
            tag_id=tag_id,
            user_id=uid,
            organization_id=organization_id,
            current_conversation_id=cid,
            has_organization_conversations_access=wide,
            includes=includes,
        )

    desc = (
        "Fetch tagged knowledge for ONE tag: pass tag_id as an INTEGER (the tag’s database id), "
        "e.g. tag_id=7 — never pass the tag title string. "
        "Optional includes: conversations, knowledge_base_documents, gallery (omit for all three). "
        "Returns other conversations (title, summary, n_messages, date; current chat excluded), "
        "accessible knowledge-base documents (id, name, brief), and gallery attachments (ids, names). "
        "Use read_knowledge_base_document / read_attachment / query_conversation to load full content. "
    )
    if wide:
        desc += (
            "This user has **organization-wide** conversation access: results include teammates’ threads in the org, "
            "not only their own. "
        )
    else:
        desc += "For this user, results are **only their own** other threads with that tag. "
    desc += (
        "Call when the user is working on a topic that matches a tag you are considering or already assigned "
        "(same app, client, project, product line) so you can align with prior threads; skip for unrelated chit-chat. "
        "If the list is empty, continue without inventing past chats."
    )

    return {
        "name": "get_tag_context",
        "description": desc,
        "parameters": GetTagContextParams,
        "function": get_tag_context,
    }
