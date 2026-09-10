import json
import uuid
from django.http import JsonResponse
from .managers import chroma_client
from django.views import View
from rest_framework.parsers import JSONParser

import logging
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.core.files.uploadedfile import SimpleUploadedFile
from .models import Document, Collection, Chunk
from api.authenticate.decorators.token_required import token_required
from .serializers import DocumentSerializer, ChunkSerializer, BigDocumentSerializer
from api.ai_layers.models import Agent
from rest_framework.parsers import MultiPartParser
from .actions import read_file_content
from api.messaging.models import Message, MessageAttachment
from api.messaging.attachment_access import user_can_access_attachment
from api.utils.color_printer import printer
from api.authenticate.services import FeatureFlagService
from django.core.exceptions import PermissionDenied
from .actions import querify_context
from .access import (
    apply_document_ownership,
    documents_accessible_q,
    parse_role_ids,
    resolve_user_organization,
    user_can_access_document,
    user_can_manage_document,
)

KB_FROM_ATTACHMENT_METADATA_KEY = "knowledge_base_document_id"

logger = logging.getLogger(__name__)

def _get_user_organization(user):
    """Get user's organization (owner or member)."""
    return resolve_user_organization(user)

def _check_train_agents_permission(user):
    """Check if user has the train-agents feature flag."""
    organization = _get_user_organization(user)
    if not organization:
        raise PermissionDenied("User has no organization.")
    enabled, _ = FeatureFlagService.is_feature_enabled(
        "train-agents", organization=organization, user=user
    )
    if not enabled:
        raise PermissionDenied("You are not allowed to manage the knowledge base. The 'train-agents' feature flag is not enabled for your organization.")

def _ownership_from_request(request, data=None):
    """
    Resolve visibility + role_ids for create/update.

    Chat uploads → always personal.
    Missing visibility → personal (chat / legacy callers).
    KB should send visibility (+ role_ids when roles).
    """
    payload = data if data is not None else request.POST
    source = (payload.get("source") or "").strip().lower()
    visibility = payload.get("visibility")
    if visibility is not None:
        visibility = str(visibility).strip().lower() or None

    role_raw = payload.get("role_ids")
    if role_raw is None and hasattr(request, "POST"):
        multi = request.POST.getlist("role_ids") if hasattr(request.POST, "getlist") else []
        if multi:
            role_raw = multi

    role_ids = parse_role_ids(role_raw)

    if source == "chat":
        return Document.Visibility.PERSONAL, [], True
    if visibility is None:
        return Document.Visibility.PERSONAL, [], False
    return visibility, role_ids, True


def _ownership_from_attachment(att: MessageAttachment):
    vis = (att.visibility or Document.Visibility.PERSONAL).strip().lower()
    if vis == MessageAttachment.Visibility.LINK:
        return Document.Visibility.PERSONAL, [], None
    if vis == Document.Visibility.ROLES:
        role_ids = [str(role.id) for role in att.allowed_roles.all()]
        return vis, role_ids, att.organization
    if vis == Document.Visibility.ORGANIZATION:
        return vis, [], att.organization
    return Document.Visibility.PERSONAL, [], None


def _attachment_index_error(att: MessageAttachment) -> str | None:
    if att.kind != "file" or not att.file:
        return "Only file attachments can be added to the knowledge base."
    ctype = (att.content_type or "").lower().split(";")[0].strip()
    if ctype.startswith("video/") or ctype.startswith("audio/"):
        return "Video and audio files cannot be added to the knowledge base."
    return None


def _uploaded_file_from_attachment(att: MessageAttachment) -> SimpleUploadedFile:
    field = att.file
    if getattr(field, "_file", None) is not None:
        try:
            field.close()
        except Exception:
            pass
        field._file = None
    with field.open("rb") as handle:
        raw = handle.read()
    name = (getattr(field, "name", None) or "file").split("/")[-1]
    return SimpleUploadedFile(
        name,
        raw,
        content_type=att.content_type or "",
    )

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class DocumentView(View):
    parser_classes = (MultiPartParser,)

    def get(self, request):
        user = request.user
        _check_train_agents_permission(user)
        documents = Document.objects.filter(documents_accessible_q(user)).distinct()

        has_file_raw = (request.GET.get("has_file") or "").strip().lower()
        if has_file_raw in {"1", "true", "yes"}:
            documents = documents.filter(file__isnull=False).exclude(file="")

        serializer = DocumentSerializer(documents, many=True, context={"request": request})
        return JsonResponse(serializer.data, safe=False)

    def post(self, request):
        _check_train_agents_permission(request.user)
        data = request.POST.copy()
        data.pop("agent_slug", None)

        file = request.FILES.get("file")

        collection, created = Collection.get_or_create_personal_collection(
            user=request.user
        )
        if not collection:
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "Collection not found",
                },
                status=400,
            )

        if not file:
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "File are required",
                },
                status=400,
            )

        try:
            file_content, file_name = read_file_content(
                file,
                content_type=getattr(file, "content_type", "") or "",
                fallback_name=(data.get("name") or "").strip() or None,
            )
        except ValueError as exc:
            logger.warning("Document upload rejected for %s: %s", file.name, exc)
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": str(exc),
                },
                status=400,
            )
        except Exception as exc:
            logger.exception(
                "Failed to read uploaded document %s (content_type=%s)",
                file.name,
                getattr(file, "content_type", ""),
            )
            from django.conf import settings

            error = (
                str(exc)
                if settings.DEBUG
                else "Failed to read the uploaded file."
            )
            return JsonResponse(
                {
                    "message": "Internal server error",
                    "error": error,
                },
                status=500,
            )

        file_content = file_content.strip()
        if not file_content:
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "The uploaded file has no extractable text content.",
                },
                status=400,
            )

        visibility, role_ids, ownership_explicit = _ownership_from_request(
            request, data
        )

        document_exists = Document.objects.filter(
            text=file_content, collection=collection
        ).exists()

        if document_exists:
            document = Document.objects.get(text=file_content, collection=collection)
            if file and not document.file:
                document.file = file
                document.content_type = getattr(file, "content_type", "") or ""
                document.save(update_fields=["file", "content_type"])
            if ownership_explicit:
                try:
                    apply_document_ownership(
                        document,
                        user=request.user,
                        visibility=visibility,
                        role_ids=role_ids,
                    )
                except ValueError as exc:
                    return JsonResponse(
                        {"message": "Bad request", "error": str(exc)},
                        status=400,
                    )

            serializer = DocumentSerializer(document, context={"request": request})
            return JsonResponse(serializer.data, status=200)

        data["collection"] = collection.id
        if not data.get("name") and file_name:
            data["name"] = file_name
        data["text"] = file_content.replace("\0", "")
        data.pop("visibility", None)
        data.pop("role_ids", None)
        data.pop("source", None)
        serializer = DocumentSerializer(data=data)

        if serializer.is_valid():
            document = serializer.save(
                file=file,
                content_type=getattr(file, "content_type", "") or "",
                created_by=request.user,
            )
            try:
                apply_document_ownership(
                    document,
                    user=request.user,
                    visibility=visibility,
                    role_ids=role_ids,
                )
            except ValueError as exc:
                document.delete()
                return JsonResponse(
                    {"message": "Bad request", "error": str(exc)},
                    status=400,
                )
            return JsonResponse(
                DocumentSerializer(document, context={"request": request}).data,
                status=201,
            )

        return JsonResponse(serializer.errors, status=400)

    def put(self, request, document_id):
        _check_train_agents_permission(request.user)
        data = json.loads(request.body)
        action = data.get("action", None)

        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document not found"}, status=404)

        if not user_can_manage_document(request.user, document):
            return JsonResponse({"error": "Document not accessible"}, status=403)

        if action == "add":
            document.add_to_rag()
        elif action == "remove":
            document.remove_from_rag()
        elif action == "generate_brief":
            document.generate_brief()
        elif action == "update_ownership" or "visibility" in data:
            visibility = data.get("visibility")
            role_ids = parse_role_ids(data.get("role_ids"))
            try:
                apply_document_ownership(
                    document,
                    user=request.user,
                    visibility=visibility,
                    role_ids=role_ids,
                )
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)
            document.refresh_from_db()

        return JsonResponse(
            DocumentSerializer(document, context={"request": request}).data, status=200
        )

    def delete(self, request, document_id):
        _check_train_agents_permission(request.user)
        try:
            document = Document.objects.get(id=document_id)
        except Document.DoesNotExist:
            return JsonResponse({"error": "Document not found"}, status=404)

        if not user_can_manage_document(request.user, document):
            return JsonResponse({"error": "Document not accessible"}, status=403)

        document.remove_from_rag()
        return JsonResponse(
            {"message": "Document deleted successfully"}, status=200
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class DocumentFromAttachmentView(View):
    def post(self, request):
        try:
            _check_train_agents_permission(request.user)
        except PermissionDenied as exc:
            return JsonResponse(
                {"message": "Forbidden", "error": str(exc)},
                status=403,
            )

        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Bad request", "error": "Invalid JSON"},
                status=400,
            )

        raw_id = data.get("attachment_id")
        try:
            attachment_id = uuid.UUID(str(raw_id))
        except (ValueError, TypeError, AttributeError):
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "attachment_id is required",
                },
                status=400,
            )

        try:
            att = MessageAttachment.objects.select_related("organization").prefetch_related(
                "allowed_roles"
            ).get(pk=attachment_id)
        except MessageAttachment.DoesNotExist:
            return JsonResponse({"error": "Attachment not found"}, status=404)

        if not user_can_access_attachment(att, user=request.user):
            return JsonResponse({"error": "Attachment not accessible"}, status=403)

        index_error = _attachment_index_error(att)
        if index_error:
            return JsonResponse(
                {"message": "Bad request", "error": index_error},
                status=400,
            )

        metadata = att.metadata if isinstance(att.metadata, dict) else {}
        existing_id = metadata.get(KB_FROM_ATTACHMENT_METADATA_KEY)
        if existing_id:
            existing = Document.objects.filter(pk=existing_id).first()
            if existing and user_can_access_document(request.user, existing):
                payload = dict(
                    DocumentSerializer(existing, context={"request": request}).data
                )
                payload["already_indexed"] = True
                return JsonResponse(payload, status=200)

        uploaded = _uploaded_file_from_attachment(att)
        try:
            file_content, file_name = read_file_content(
                uploaded,
                content_type=att.content_type or "",
                fallback_name=uploaded.name,
            )
        except ValueError as exc:
            return JsonResponse(
                {"message": "Bad request", "error": str(exc)},
                status=400,
            )

        file_content = file_content.strip().replace("\0", "")
        if not file_content:
            return JsonResponse(
                {
                    "message": "Bad request",
                    "error": "The uploaded file has no extractable text content.",
                },
                status=400,
            )

        collection, _ = Collection.get_or_create_personal_collection(
            user=request.user
        )
        visibility, role_ids, organization = _ownership_from_attachment(att)
        serializer = DocumentSerializer(
            data={
                "collection": collection.id,
                "name": file_name,
                "text": file_content,
            }
        )
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        uploaded.seek(0)
        document = serializer.save(
            file=uploaded,
            content_type=att.content_type or "",
            created_by=request.user,
        )
        try:
            apply_document_ownership(
                document,
                user=request.user,
                visibility=visibility,
                role_ids=role_ids,
                organization=organization,
            )
        except ValueError:
            apply_document_ownership(
                document,
                user=request.user,
                visibility=Document.Visibility.PERSONAL,
            )

        metadata = dict(metadata)
        metadata[KB_FROM_ATTACHMENT_METADATA_KEY] = document.id
        att.metadata = metadata
        att.save(update_fields=["metadata"])

        payload = dict(
            DocumentSerializer(document, context={"request": request}).data
        )
        payload["already_indexed"] = False
        return JsonResponse(payload, status=201)


@csrf_exempt
@token_required
def sync_drive_document(request, document_id):
    """
    POST /v1/rag/documents/<id>/sync-drive/

    Re-download content from Google Drive and re-index the document.
    """
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        _check_train_agents_permission(request.user)
    except Exception as exc:
        return JsonResponse({"error": str(exc)}, status=403)

    try:
        document = Document.objects.select_related("collection", "drive_integration").get(
            id=document_id
        )
    except Document.DoesNotExist:
        return JsonResponse({"error": "Document not found"}, status=404)

    if not user_can_manage_document(request.user, document):
        return JsonResponse({"error": "Document not accessible"}, status=403)

    if not document.drive_file_id:
        return JsonResponse({"error": "Document is not linked to Google Drive"}, status=400)

    from api.integrations.drive_import import sync_document_from_drive
    from api.integrations.providers import IntegrationProviderError

    try:
        document = sync_document_from_drive(document)
    except IntegrationProviderError as exc:
        return JsonResponse({"error": str(exc)}, status=400)

    return JsonResponse(
        DocumentSerializer(document, context={"request": request}).data,
        status=200,
    )

@csrf_exempt
@token_required
def query_collection(request):
    data = json.loads(request.body)
    conversation_id = data.get("conversation_id", None)
    document_id = data.get("document_id", None)
    query_text = data.get("query", None)
    collection_id = data.get("collection_id", None)

    collection = Collection.objects.get(user=request.user, pk=collection_id)

    if collection:
        messages = Message.objects.filter(conversation=conversation_id).order_by("-id")[
            :4
        ]

        if document_id:
            document = Document.objects.get(id=document_id)

        _context = f"""
        These are the last four messages in the conversation:
        ---
        {" ".join([f'{m.type}: {m.text}' for m in messages])}
        ---

        This is the last user message text: {query_text}
        """

        if document:
            _context += f"""
            This is a brief from the document the user wants to query: 
            ---
            {document.brief}
            ---
            """

        queries = querify_context(context=_context)
        printer.success(
            "There is a collection for the user, getting results from Chroma"
        )

        printer.blue(f"Queries: {queries.queries}")
        printer.yellow(f"Document: {document}")
        results = chroma_client.get_results(
            collection_name=collection.slug, query_texts=queries.queries, n_results=4
        )

        data = {"results": results}
        return JsonResponse(data, safe=False)

    return JsonResponse({"error": "No collection found"}, status=404)

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ChunkSetView(View):
    def get(self, request, document_id):
        document = Document.objects.get(id=document_id)
        data = BigDocumentSerializer(document).data
        return JsonResponse(data, status=201)

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ChunkDetailView(View):
    parser_classes = (JSONParser,)

    def get(self, request, chunk_id):
        try:
            chunk = Chunk.objects.get(id=chunk_id)
            serializer = ChunkSerializer(chunk)
            return JsonResponse(serializer.data, safe=False, status=200)
        except Chunk.DoesNotExist:
            return JsonResponse({"error": "Chunk not found"}, status=404)

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class QueryDocument(View):
    def post(self, request, document_id):
        data = json.loads(request.body)
        query_text = data.get("query", None)
        conversation_id = data.get("conversation_id", None)

        document = Document.objects.get(id=document_id)
        collection = document.collection

        messages = Message.objects.filter(conversation=conversation_id).order_by("-id")[
            :4
        ]

        _context = f"""
        These are the last four messages in the conversation:
        ---
        {" ".join([f'{m.type}: {m.text}' for m in messages])}
        ---

        This is a summary of the document the user wants to query:
        ---
        {document.brief}
        ---

        This is the last user message text: {query_text}
        """

        queries = querify_context(context=_context)
        printer.success(
            "There is a collection for the user, getting results from Chroma"
        )

        printer.blue(f"Queries: {queries.queries}")
        printer.yellow(f"Document: {document}")

        results = chroma_client.get_results(
            collection_name=collection.slug,
            query_texts=queries.queries,
            n_results=4,
            where={"extra": document.get_representation()},
        )

        data = {"results": results}
        return JsonResponse(data, safe=False)

@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class QueryCompletions(View):
    def post(self, request):
        data = json.loads(request.body)
        query_text = data.get("query", None)
        agent_slug = data.get("agent_slug", None)

        agent = Agent.objects.get(slug=agent_slug)

        if not agent:
            return JsonResponse({"error": "Agent not found"}, status=404)
        collection, created = Collection.get_or_create_agent_collection(agent=agent)
        if created:
            printer.success("No collection found for the agent, creating a new one")
            return JsonResponse([], status=200, safe=False)

        queries = querify_context(context=query_text)
        printer.success(
            "There is a collection for the agent, getting results from Chroma"
        )

        results = chroma_client.get_results(
            collection_name=collection.slug,
            query_texts=queries.queries,
            n_results=4,
        )

        data = {"results": results}
        return JsonResponse(data, safe=False)
