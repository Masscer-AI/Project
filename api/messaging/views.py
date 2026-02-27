from datetime import timedelta
from functools import reduce
from operator import or_
from django.utils import timezone
from django.db.models import Q, Count

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views import View
from .models import (
    Conversation,
    Message,
    MessageAttachment,
    SharedConversation,
    ChatWidget,
    WidgetVisitorSession,
    ConversationAlert,
    ConversationAlertRule,
    Tag,
)
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
    BigConversationSerializer,
    SharedConversationSerializer,
    ChatWidgetConfigSerializer,
    ChatWidgetSerializer,
    ConversationAlertSerializer,
    ConversationAlertRuleSerializer,
    TagSerializer,
)
from api.authenticate.models import Organization
from api.authenticate.services import FeatureFlagService
from django.core.exceptions import PermissionDenied
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
import base64
import json
from api.authenticate.decorators.token_required import token_required
from api.authenticate.decorators.widget_session_required import (
    create_widget_session_token,
    widget_session_required,
)
from .actions import transcribe_audio, complete_message
from django.core.files.storage import FileSystemStorage
import os
import uuid
from django.conf import settings
from django.core.cache import cache


def _get_conversation_for_user(request, conversation_id):
    """
    Get conversation if the user has access (owns it or is org member).
    Returns (conversation, None) on success, or (None, JsonResponse) on 404.
    """
    try:
        conversation = Conversation.objects.get(id=conversation_id)
    except Conversation.DoesNotExist:
        return None, JsonResponse(
            {"message": "Conversation not found", "status": 404}, status=404
        )
    if conversation.status == "deleted":
        return None, JsonResponse(
            {"message": "Conversation not found", "status": 404}, status=404
        )
    user = request.user
    if _user_can_access_conversation(user, conversation):
        return conversation, None
    return None, JsonResponse(
        {"message": "Conversation not found", "status": 404}, status=404
    )


def _get_org_user_ids(user):
    """Get all user IDs in the user's organization(s). Returns None if user has no org (fallback to own only)."""
    owned_orgs = Organization.objects.filter(owner=user)
    member_orgs = Organization.objects.none()
    if hasattr(user, "profile") and user.profile.organization_id:
        member_orgs = Organization.objects.filter(id=user.profile.organization_id)
    orgs = (owned_orgs | member_orgs).distinct()
    if not orgs.exists():
        return None
    owner_ids = set(Organization.objects.filter(id__in=orgs).values_list("owner_id", flat=True))
    member_ids = set(
        User.objects.filter(profile__organization__in=orgs).values_list(
            "id", flat=True
        )
    )
    return list(owner_ids | member_ids)


def _user_can_access_conversation(user, conversation):
    if conversation.user_id == user.id:
        return True
    org_user_ids = _get_org_user_ids(user)
    widget_owner_id = (
        conversation.chat_widget.created_by_id if conversation.chat_widget else None
    )
    if org_user_ids and (
        conversation.user_id in org_user_ids
        or (conversation.user_id is None and widget_owner_id in org_user_ids)
    ):
        return True
    return False


def _build_conversation_list_queryset(request, user):
    """
    Build the filtered, annotated, ordered queryset for conversation list.
    Returns a queryset or JsonResponse on validation error.
    """
    scope = request.GET.get("scope", "org")
    chat_widget_id = (request.GET.get("chat_widget_id") or "").strip()
    status_param = (request.GET.get("status") or "").strip().lower()

    if scope == "personal":
        conversations = Conversation.objects.filter(user=user)
    else:
        org_user_ids = _get_org_user_ids(user)
        if org_user_ids:
            conversations = Conversation.objects.filter(
                Q(user_id__in=org_user_ids)
                | Q(
                    user__isnull=True,
                    chat_widget__created_by_id__in=org_user_ids,
                )
            )
        else:
            conversations = Conversation.objects.filter(user=user)

    # Status filter
    if status_param in ("", "active_inactive"):
        conversations = conversations.filter(status__in=["active", "inactive"])
    elif status_param == "all":
        conversations = conversations.exclude(status="deleted")
    elif status_param in ("active", "inactive", "archived", "deleted"):
        conversations = conversations.filter(status=status_param)
    else:
        return JsonResponse(
            {
                "message": "status must be one of: active_inactive, all, active, inactive, archived, deleted",
                "status": 400,
            },
            status=400,
        )

    # Chat widget filter
    if chat_widget_id:
        if chat_widget_id.lower() == "none":
            conversations = conversations.filter(chat_widget__isnull=True)
        else:
            try:
                widget_id = int(chat_widget_id)
                conversations = conversations.filter(chat_widget_id=widget_id)
            except ValueError:
                return JsonResponse(
                    {
                        "message": "chat_widget_id must be an integer or 'none'",
                        "status": 400,
                    },
                    status=400,
                )

    # Search (title, id, summary)
    search = (request.GET.get("search") or "").strip()
    if search:
        search_q = Q()
        if search:
            search_q = (
                Q(title__icontains=search)
                | Q(id__icontains=search)
                | Q(summary__icontains=search)
            )
        conversations = conversations.filter(search_q)

    # User filter
    user_id_param = (request.GET.get("user_id") or "").strip()
    if user_id_param and user_id_param.isdigit():
        conversations = conversations.filter(user_id=int(user_id_param))

    # Date range (accepts YYYY-MM-DD or ISO)
    date_from = (request.GET.get("date_from") or "").strip()
    if date_from:
        try:
            from datetime import datetime as dt_module
            if len(date_from) == 10 and date_from[4] == "-" and date_from[7] == "-":
                dt = dt_module.strptime(date_from, "%Y-%m-%d")
            else:
                dt = dt_module.fromisoformat(date_from.replace("Z", "+00:00"))
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            conversations = conversations.filter(created_at__gte=dt)
        except (ValueError, TypeError):
            pass
    date_to = (request.GET.get("date_to") or "").strip()
    if date_to:
        try:
            from datetime import datetime as dt_module
            if len(date_to) == 10 and date_to[4] == "-" and date_to[7] == "-":
                dt = dt_module.strptime(date_to, "%Y-%m-%d").replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
            else:
                dt = dt_module.fromisoformat(date_to.replace("Z", "+00:00"))
                dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)
            if timezone.is_naive(dt):
                dt = timezone.make_aware(dt)
            conversations = conversations.filter(created_at__lte=dt)
        except (ValueError, TypeError):
            pass

    # Tags filter (conversations that have any of these tag ids)
    tags_param = (request.GET.get("tags") or "").strip()
    if tags_param:
        tag_ids = []
        for x in tags_param.split(","):
            if x.strip().isdigit():
                tag_ids.append(int(x.strip()))
        if tag_ids:
            tag_qs = [Q(tags__contains=[tid]) for tid in tag_ids]
            conversations = conversations.filter(reduce(or_, tag_qs))

    # Alert rules filter (conversations that have alerts from any of these rules)
    alert_rules_param = (request.GET.get("alert_rules") or "").strip()
    if alert_rules_param:
        rule_ids = [x.strip() for x in alert_rules_param.split(",") if x.strip()]
        if rule_ids:
            conversations = conversations.filter(
                alerts__alert_rule_id__in=rule_ids
            ).distinct()

    # Min/max messages – annotate and filter (exclude 0-message convos by default)
    conversations = conversations.annotate(msg_count=Count("messages"))
    min_messages = request.GET.get("min_messages")
    if min_messages is not None and str(min_messages).strip().isdigit():
        min_val = max(1, int(min_messages))
        conversations = conversations.filter(msg_count__gte=min_val)
    else:
        conversations = conversations.filter(msg_count__gt=0)
    max_messages = request.GET.get("max_messages")
    if max_messages is not None and str(max_messages).isdigit():
        conversations = conversations.filter(msg_count__lte=int(max_messages))

    # Sort
    sort_by = (request.GET.get("sort_by") or "newest").lower()
    messages_sort = (request.GET.get("messages_sort") or "none").lower()
    if messages_sort in ("asc", "desc"):
        order = "msg_count" if messages_sort == "asc" else "-msg_count"
        conversations = conversations.order_by(order, "-created_at")
    else:
        if sort_by == "oldest":
            conversations = conversations.order_by("created_at", "id")
        else:
            conversations = conversations.order_by("-created_at", "-id")

    return conversations


def _rate_limit_widget_request(
    *,
    request,
    scope_key: str,
    limit: int,
    window_seconds: int,
):
    remote_addr = request.META.get("REMOTE_ADDR", "unknown")
    key = f"widget-rate:{scope_key}:{remote_addr}"
    current = cache.get(key)
    if current is None:
        cache.set(key, 1, timeout=window_seconds)
        return None
    if int(current) >= limit:
        return JsonResponse(
            {"error": "Too many requests. Please try again later."},
            status=429,
        )
    cache.incr(key)
    return None


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ConversationStatsView(View):
    """Separate endpoint for dashboard metrics. Accepts same filters as list for consistency."""

    def get(self, request):
        user = request.user
        conversations = _build_conversation_list_queryset(request, user)
        if isinstance(conversations, JsonResponse):
            return conversations

        total_conversations = conversations.count()
        agg = conversations.aggregate(total_msgs=Count("messages"))
        total_messages = agg.get("total_msgs") or 0

        now = timezone.now()
        week_ago = now - timedelta(days=7)
        last_7_days = conversations.filter(created_at__gte=week_ago).count()

        # Per-day breakdown for last 7 days (for chart)
        from django.db.models.functions import TruncDate
        last_7_days_breakdown = list(
            conversations.filter(created_at__gte=week_ago)
            .annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .values_list("day", "count")
        )
        day_counts = {str(d): c for d, c in last_7_days_breakdown if d}
        week_points = []
        for i in range(7):
            d = (now - timedelta(days=(6 - i))).date()
            week_points.append({"date": d.isoformat(), "count": day_counts.get(str(d), 0)})

        top_users_rows = (
            conversations.exclude(user_id__isnull=True)
            .values("user_id")
            .annotate(
                conv_count=Count("id", distinct=True),
                msg_count=Count("messages"),
            )
            .order_by("-conv_count", "-msg_count")[:5]
        )
        user_ids = [r["user_id"] for r in top_users_rows]
        user_map = {u.id: u.username for u in User.objects.filter(id__in=user_ids)}
        top_users = [
            {
                "user_id": r["user_id"],
                "label": user_map.get(r["user_id"]) or f"User {r['user_id']}",
                "conversations": r["conv_count"],
                "messages": r["msg_count"],
            }
            for r in top_users_rows
        ]

        return JsonResponse(
            {
                "total_conversations": total_conversations,
                "total_messages": total_messages,
                "last_7_days": last_7_days,
                "last_7_days_breakdown": week_points,
                "top_users": top_users,
            },
            safe=False,
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ConversationView(View):
    def get(self, request, *args, **kwargs):
        user = request.user
        conversation_id = kwargs.get("id")
        if conversation_id:
            conversation, err = _get_conversation_for_user(request, conversation_id)
            if err:
                return err
            serialized_conversation = BigConversationSerializer(
                conversation, context={"request": request}
            ).data
            return JsonResponse(serialized_conversation, safe=False)
        else:
            conversations = _build_conversation_list_queryset(request, user)
            if isinstance(conversations, JsonResponse):
                return conversations

            # Filter options for user dropdown (from full filtered set, before pagination)
            user_ids = list(
                conversations.values_list("user_id", flat=True).distinct()
            )[:100]
            user_ids = [uid for uid in user_ids if uid is not None]
            user_options = (
                list(User.objects.filter(id__in=user_ids).values("id", "username"))
                if user_ids
                else []
            )

            # Pagination
            limit = min(max(1, int(request.GET.get("limit", 50))), 100)
            offset = max(0, int(request.GET.get("offset", 0)))
            total = conversations.count()
            conversations = conversations[offset : offset + limit]

            serialized_conversations = ConversationSerializer(
                conversations, many=True, context={"request": request}
            ).data

            return JsonResponse(
                {
                    "results": serialized_conversations,
                    "total": total,
                    "limit": limit,
                    "offset": offset,
                    "has_next": offset + limit < total,
                    "filter_options": {
                        "users": [
                            {"id": u["id"], "label": u["username"] or f"User {u['id']}"}
                            for u in user_options
                        ],
                    },
                },
                safe=False,
            )

    def post(self, request, *args, **kwargs):
        user = request.user

        existing_conversation = Conversation.objects.filter(
            user=user, messages__isnull=True, status__in=["active", "inactive"]
        ).first()
        if existing_conversation:
            data = BigConversationSerializer(existing_conversation, context={'request': request}).data
            return JsonResponse(data, status=200)

        conversation = Conversation.objects.create(user=user)
        data = BigConversationSerializer(conversation, context={'request': request}).data
        return JsonResponse(data, status=201)

    def put(self, request, *args, **kwargs):
        user = request.user
        data = json.loads(request.body)
        conversation_id = kwargs.get("id")

        conversation, err = _get_conversation_for_user(request, conversation_id)
        if err:
            return err

        regenerate = data.get("regenerate", None)
        if regenerate:
            conversation.cut_from(regenerate["user_message_id"])
            return JsonResponse({"status": "regenerated"})

        try:
            # Validate and sanitize tags if present
            if "tags" in data:
                raw_tags = data["tags"]
                if not isinstance(raw_tags, list):
                    return JsonResponse(
                        {"message": "Tags must be a list of tag IDs"}, status=400
                    )
                # Coerce to integers, discard any non-numeric values
                tag_ids = []
                for t in raw_tags:
                    try:
                        tag_ids.append(int(t))
                    except (ValueError, TypeError):
                        continue
                # Only keep IDs that actually exist as enabled Tags
                if tag_ids:
                    valid_ids = list(
                        Tag.objects.filter(id__in=tag_ids, enabled=True)
                        .values_list("id", flat=True)
                    )
                else:
                    valid_ids = []
                data["tags"] = valid_ids

            # Whitelist of allowed fields to update
            ALLOWED_FIELDS = {"title", "tags", "background_image_src"}
            for key, value in data.items():
                if key in ALLOWED_FIELDS:
                    setattr(conversation, key, value)

            # Save the updated instance
            conversation.save()

            # Serialize the updated conversation
            serialized_data = ConversationSerializer(conversation, context={'request': request}).data
            return JsonResponse(serialized_data, status=200)
        except Conversation.DoesNotExist:
            return JsonResponse(
                {"message": "Conversation not found", "status": 404}, status=404
            )


    def delete(self, request, *args, **kwargs):
        conversation_id = kwargs.get("id")
        conversation, err = _get_conversation_for_user(request, conversation_id)
        if err:
            return err
        conversation.status = "deleted"
        conversation.deleted_at = timezone.now()
        conversation.save(update_fields=["status", "deleted_at", "updated_at"])
        return JsonResponse({"status": "deleted"})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ConversationBulkView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"message": "Invalid JSON", "status": 400}, status=400)

        action = (data.get("action") or "").strip().lower()
        conversation_ids = data.get("conversation_ids") or []
        if action not in ("archive", "unarchive", "delete"):
            return JsonResponse(
                {"message": "action must be archive, unarchive, or delete", "status": 400},
                status=400,
            )
        if not isinstance(conversation_ids, list) or not conversation_ids:
            return JsonResponse(
                {"message": "conversation_ids must be a non-empty list", "status": 400},
                status=400,
            )

        updated = 0
        skipped = 0
        now = timezone.now()
        inactive_threshold = now - timedelta(days=30)
        user = request.user
        conversations = Conversation.objects.filter(id__in=conversation_ids).select_related(
            "chat_widget"
        )
        by_id = {str(c.id): c for c in conversations}

        for conv_id in conversation_ids:
            conversation = by_id.get(str(conv_id))
            if not conversation:
                skipped += 1
                continue
            if not _user_can_access_conversation(user, conversation):
                skipped += 1
                continue

            if action == "archive":
                conversation.status = "archived"
                conversation.archived_at = now
                conversation.deleted_at = None
            elif action == "unarchive":
                is_recent = bool(
                    conversation.last_message_at and conversation.last_message_at >= inactive_threshold
                )
                conversation.status = "active" if is_recent else "inactive"
                conversation.archived_at = None
                conversation.deleted_at = None
            else:  # delete
                conversation.status = "deleted"
                conversation.deleted_at = now
            conversation.save(update_fields=["status", "archived_at", "deleted_at", "updated_at"])
            updated += 1

        return JsonResponse(
            {"status": "ok", "action": action, "updated": updated, "skipped": skipped},
            status=200,
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class MessageView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Invalid JSON", "status": 400}, status=400
            )
        conversation_id = data.get("conversation")

        if not conversation_id:
            return JsonResponse(
                {"message": "conversation is required", "status": 400}, status=400
            )

        try:
            conversation = Conversation.objects.get(
                id=conversation_id, user=request.user
            )
        except Conversation.DoesNotExist:
            return JsonResponse(
                {"message": "Conversation not found", "status": 404}, status=404
            )

        if not conversation.title and data["type"] == "assistant":
            conversation.generate_title()

        serializer = MessageSerializer(data=data)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=201)
        else:
            return JsonResponse(serializer.errors, status=400)

    def put(self, request, *args, **kwargs):
        data = json.loads(request.body)
        message_id = kwargs.get("id")

        try:
            message = Message.objects.get(
                id=message_id, conversation__user=request.user
            )
        except Message.DoesNotExist:
            return JsonResponse(
                {"message": "Message not found", "status": 404}, status=404
            )

        serializer = MessageSerializer(message, data=data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse({"status": "updated"})
        else:
            return JsonResponse(serializer.errors, status=400)

    def delete(self, request, *args, **kwargs):
        message_id = kwargs.get("id")

        try:
            message = Message.objects.get(
                id=message_id, conversation__user=request.user
            )
            message.delete()
            return JsonResponse({"status": "deleted"})
        except Message.DoesNotExist:
            return JsonResponse(
                {"message": "Message not found", "status": 404}, status=404
            )


@csrf_exempt
def upload_audio(request):
    if request.method == "POST" and request.FILES.get("audio_file"):
        audio_file = request.FILES["audio_file"]

        random_filename = f"{uuid.uuid4()}{os.path.splitext(audio_file.name)[1]}"

        fs = FileSystemStorage(
            location=os.path.join(settings.MEDIA_ROOT, "audio_files")
        )
        filename = fs.save(random_filename, audio_file)
        file_path = fs.path(filename)

        transcription = transcribe_audio(file_path)

        # Generate speech from the transcription
        # speech_output_path = os.path.join(
        #     settings.MEDIA_ROOT, "audio_files", f"{random_filename_speech}"
        # )
        # audio_data = generate_speech_api(transcription, speech_output_path)

        # with open(speech_output_path, "rb") as audio_file:
        #     audio_data = audio_file.read()
        # print(audio_data, "AUDIO DATA")
        return JsonResponse(
            {
                "transcription": transcription,
                # "speech_audio": audio_data.decode("latin-1"),
            }
        )

    return JsonResponse({"error": "Invalid request"}, status=400)


@csrf_exempt
@token_required
def upload_message_attachments(request):
    """
    Upload file attachments for a message (images, audio, etc.).
    Accepts JSON: { conversation_id, attachments: [{ content: "data:...;base64,...", name }] }
    Returns: { attachments: [{ id, url }] }
    Files expire after 30 days.
    """
    if request.user is None:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    conversation_id = data.get("conversation_id")
    attachments_data = data.get("attachments", [])

    if not conversation_id:
        return JsonResponse({"error": "conversation_id is required"}, status=400)
    if not attachments_data or not isinstance(attachments_data, list):
        return JsonResponse({"error": "attachments must be a non-empty list"}, status=400)

    conv, err = _get_conversation_for_user(request, conversation_id)
    if err:
        return err

    result = []
    for i, att in enumerate(attachments_data):
        if not isinstance(att, dict):
            return JsonResponse(
                {"error": f"attachments[{i}] must be an object"}, status=400
            )
        content = att.get("content", "")
        name = att.get("name", f"file_{i}")

        if not content or not content.startswith("data:"):
            return JsonResponse(
                {"error": f"attachments[{i}].content must be a data URL (data:...;base64,...)"},
                status=400,
            )

        try:
            header, b64_data = content.split(",", 1)
            ext = "bin"
            if "image/png" in header or "png" in header:
                ext = "png"
            elif "image/jpeg" in header or "jpeg" in header or "jpg" in header:
                ext = "jpg"
            elif "image/gif" in header or "gif" in header:
                ext = "gif"
            elif "image/webp" in header or "webp" in header:
                ext = "webp"
            elif "audio" in header:
                ext = "webm" if "webm" in header else "mp3" if "mp3" in header else "wav"
            elif "application/pdf" in header or "pdf" in header:
                ext = "pdf"
            elif "wordprocessingml" in header or "docx" in header:
                ext = "docx"
            elif "msword" in header or "doc" in header:
                ext = "doc"
            elif "text/plain" in header or "plain" in header:
                ext = "txt"
            elif "text/html" in header or "html" in header:
                ext = "html"
            raw = base64.b64decode(b64_data)
        except Exception as e:
            return JsonResponse(
                {"error": f"attachments[{i}] invalid base64: {e}"}, status=400
            )

        from django.core.files.base import ContentFile

        file_obj = ContentFile(raw, name=f"{uuid.uuid4().hex}.{ext}")
        if att.get("content_type"):
            content_type = att["content_type"]
        elif ext in ("png", "jpg", "gif", "webp"):
            content_type = f"image/{ext}"
        elif ext in ("webm", "mp3", "wav"):
            content_type = f"audio/{ext}"
        elif ext == "pdf":
            content_type = "application/pdf"
        elif ext == "docx":
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ext == "doc":
            content_type = "application/msword"
        elif ext == "txt":
            content_type = "text/plain"
        elif ext == "html":
            content_type = "text/html"
        else:
            content_type = "application/octet-stream"
        attachment = MessageAttachment.objects.create(
            conversation=conv,
            user=request.user,
            kind="file",
            file=file_obj,
            content_type=content_type,
        )
        url = request.build_absolute_uri(attachment.file.url)
        result.append({"id": str(attachment.id), "url": url})

    return JsonResponse({"attachments": result})


@csrf_exempt
@token_required
def link_message_attachment(request):
    """
    Create a reference attachment (no file upload).

    Accepts JSON:
      { conversation_id, kind: "rag_document"|"website", rag_document_id?, url? }

    Returns:
      { attachment: { id } }
    """
    if request.user is None:
        return JsonResponse({"error": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON"}, status=400)

    conversation_id = data.get("conversation_id")
    kind = data.get("kind")
    if not conversation_id:
        return JsonResponse({"error": "conversation_id is required"}, status=400)
    if kind not in ("rag_document", "website"):
        return JsonResponse(
            {"error": "kind must be one of: rag_document, website"},
            status=400,
        )

    conv, err = _get_conversation_for_user(request, conversation_id)
    if err:
        return err

    if kind == "rag_document":
        rag_document_id = data.get("rag_document_id") or data.get("document_id")
        if rag_document_id is None:
            return JsonResponse({"error": "rag_document_id is required"}, status=400)
        try:
            from api.rag.models import Document

            doc = Document.objects.select_related("collection").get(id=int(rag_document_id))
        except Exception:
            return JsonResponse({"error": "RAG document not found"}, status=404)

        if getattr(doc.collection, "user_id", None) != request.user.id:
            return JsonResponse({"error": "RAG document not accessible"}, status=403)

        attachment = MessageAttachment.objects.create(
            conversation=conv,
            user=request.user,
            kind="rag_document",
            rag_document=doc,
            content_type="application/rag_document",
            expires_at=None,
        )
        return JsonResponse({"attachment": {"id": str(attachment.id)}})

    # kind == "website"
    url = data.get("url")
    if not url:
        return JsonResponse({"error": "url is required"}, status=400)

    # Snapshot content via Firecrawl so the agent can read without refetch.
    snapshot_content = None
    snapshot_title = None
    snapshot_source_url = url
    try:
        from firecrawl import Firecrawl
        from django.conf import settings

        if not getattr(settings, "FIRECRAWL_API_KEY", None):
            raise RuntimeError("FIRECRAWL_API_KEY is not configured")
        firecrawl = Firecrawl(api_key=settings.FIRECRAWL_API_KEY)
        scrape = firecrawl.scrape(url, formats=["markdown"])

        # SDK shape varies; normalize.
        if isinstance(scrape, dict):
            snapshot_content = (
                scrape.get("markdown")
                or (scrape.get("data") or {}).get("markdown")
            )
            meta = scrape.get("metadata") or (scrape.get("data") or {}).get("metadata") or {}
            snapshot_title = meta.get("title")
            snapshot_source_url = meta.get("sourceURL") or meta.get("source_url") or url
        else:
            snapshot_content = getattr(scrape, "markdown", None)
            meta = getattr(scrape, "metadata", None) or {}
            if isinstance(meta, dict):
                snapshot_title = meta.get("title")
                snapshot_source_url = meta.get("sourceURL") or meta.get("source_url") or url
    except Exception:
        # If Firecrawl fails, still create the attachment with just URL.
        snapshot_content = None

    attachment = MessageAttachment.objects.create(
        conversation=conv,
        user=request.user,
        kind="website",
        url=url,
        content_type="text/html",
        expires_at=None,
        metadata={
            "content": snapshot_content,
            "title": snapshot_title,
            "source_url": snapshot_source_url,
            "fetched_at": timezone.now().isoformat(),
            "provider": "firecrawl",
        },
    )
    return JsonResponse(
        {
            "attachment": {
                "id": str(attachment.id),
                "url": url,
                "title": snapshot_title,
            }
        }
    )


@csrf_exempt
def get_suggestion(request):
    data = json.loads(request.body)
    # print(data.get("input"), "INPUT TO GET SUGGESTION")
    suggestion = complete_message(data.get("input"))
    return JsonResponse({"suggestion": suggestion})


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="post")
class SharedConversationView(View):
    def get(self, request, share_id):
        try:
            shared_conversation = SharedConversation.objects.get(id=share_id)
        except SharedConversation.DoesNotExist:
            return JsonResponse(
                {"message": "Share not found", "status": 404}, status=404
            )

        serialized_conversation = SharedConversationSerializer(shared_conversation, context={'request': request}).data
        return JsonResponse(serialized_conversation, safe=False)

    def post(self, request, *args, **kwargs):
        data = json.loads(request.body)
        conversation_id = data.get("conversation")
        valid_until = data.get("valid_until", None)

        print(conversation_id, valid_until, "CONVERSATION ID AND VALID UNTIL")
        if not conversation_id:
            return JsonResponse(
                {"message": "conversation is required", "status": 400}, status=400
            )

        try:
            conversation = Conversation.objects.get(
                id=conversation_id, user=request.user
            )
        except Conversation.DoesNotExist:
            return JsonResponse(
                {"message": "Conversation not found", "status": 404}, status=404
            )

        if not valid_until:
            # Default to 30 days
            valid_until = timezone.now() + timedelta(days=30)
        shared_conversation = SharedConversation.objects.create(
            conversation=conversation, user=request.user, valid_until=valid_until
        )

        return JsonResponse(
            {"status": "created", "id": shared_conversation.id}, status=201
        )


@method_decorator(csrf_exempt, name="dispatch")
class ChatWidgetConfigView(View):
    def get(self, request, token):
        try:
            widget = ChatWidget.objects.get(token=token, enabled=True)
        except ChatWidget.DoesNotExist:
            return JsonResponse(
                {"error": "Widget not found or disabled", "status": 404}, status=404
            )

        serializer = ChatWidgetConfigSerializer(widget)
        return JsonResponse(serializer.data, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
class ChatWidgetSessionView(View):
    def get(self, request, token):
        rate_limit_resp = _rate_limit_widget_request(
            request=request,
            scope_key=f"session:{token}",
            limit=120,
            window_seconds=60,
        )
        if rate_limit_resp:
            return rate_limit_resp

        try:
            widget = ChatWidget.objects.get(token=token, enabled=True)
        except ChatWidget.DoesNotExist:
            return JsonResponse(
                {"error": "Widget not found or disabled", "status": 404}, status=404
            )

        visitor_id = (request.GET.get("visitor_id") or "").strip()
        if not visitor_id:
            visitor_id = uuid.uuid4().hex
        visitor_id = visitor_id[:64]

        now = timezone.now()
        expires_at = now + timedelta(days=30)
        defaults = {
            "origin": (request.headers.get("Origin") or "")[:255],
            "user_agent": request.headers.get("User-Agent") or "",
            "expires_at": expires_at,
        }
        session, _ = WidgetVisitorSession.objects.get_or_create(
            widget=widget,
            visitor_id=visitor_id,
            defaults=defaults,
        )
        if session.is_blocked:
            return JsonResponse({"error": "Widget session blocked"}, status=403)

        # Keep session alive for persistent browser identity.
        session.expires_at = expires_at
        session.origin = defaults["origin"]
        session.user_agent = defaults["user_agent"]
        session.save(update_fields=["expires_at", "origin", "user_agent", "last_seen_at"])

        auth_token = create_widget_session_token(
            widget_token=widget.token,
            session_id=str(session.id),
            visitor_id=session.visitor_id,
        )

        return JsonResponse(
            {
                "token": auth_token,
                "token_type": "WidgetSession",
                "visitor_id": session.visitor_id,
                "session_id": str(session.id),
                "expires_at": session.expires_at.isoformat(),
            },
            safe=False,
        )


def _get_widget_organization(widget):
    owner = getattr(widget, "created_by", None)
    if not owner:
        return None
    owned_org = Organization.objects.filter(owner=owner).first()
    if owned_org:
        return owned_org
    if hasattr(owner, "profile") and owner.profile.organization:
        return owner.profile.organization
    return None


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(widget_session_required, name="dispatch")
class ChatWidgetConversationView(View):
    def post(self, request, token):
        rate_limit_resp = _rate_limit_widget_request(
            request=request,
            scope_key=f"conversation:{token}",
            limit=30,
            window_seconds=60,
        )
        if rate_limit_resp:
            return rate_limit_resp

        if request.widget.token != token:
            return JsonResponse({"error": "Widget token mismatch"}, status=403)

        session = request.widget_visitor_session
        existing_conversation = Conversation.objects.filter(
            widget_visitor_session=session,
            messages__isnull=True,
            status__in=["active", "inactive"],
        ).first()
        if existing_conversation:
            data = BigConversationSerializer(
                existing_conversation, context={"request": request}
            ).data
            return JsonResponse(data, status=200)

        conversation = Conversation.objects.create(
            user=None,
            organization=_get_widget_organization(request.widget),
            chat_widget=request.widget,
            widget_visitor_session=session,
        )
        data = BigConversationSerializer(conversation, context={"request": request}).data
        return JsonResponse(data, status=201)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(widget_session_required, name="dispatch")
class ChatWidgetAgentTaskView(View):
    def post(self, request, token):
        rate_limit_resp = _rate_limit_widget_request(
            request=request,
            scope_key=f"agent-task:{token}",
            limit=20,
            window_seconds=60,
        )
        if rate_limit_resp:
            return rate_limit_resp

        if request.widget.token != token:
            return JsonResponse({"error": "Widget token mismatch"}, status=403)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body"}, status=400)

        conversation_id = data.get("conversation_id")
        user_inputs = data.get("user_inputs")
        if not conversation_id or not isinstance(user_inputs, list) or not user_inputs:
            return JsonResponse(
                {
                    "error": "conversation_id and user_inputs (non-empty list) are required"
                },
                status=400,
            )

        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                chat_widget=request.widget,
                widget_visitor_session=request.widget_visitor_session,
            )
        except Conversation.DoesNotExist:
            return JsonResponse({"error": "Conversation not found"}, status=404)

        if not request.widget.agent:
            return JsonResponse({"error": "Widget has no configured agent"}, status=400)

        tool_names = ["read_attachment", "list_attachments"]
        if request.widget.web_search_enabled:
            tool_names.append("explore_web")
        if request.widget.rag_enabled:
            tool_names.append("rag_query")
        tool_names.extend(request.widget.plugins_enabled or [])

        from api.messaging.tasks import widget_conversation_agent_task

        task = widget_conversation_agent_task.delay(
            conversation_id=str(conversation.id),
            user_inputs=user_inputs,
            tool_names=tool_names,
            agent_slug=request.widget.agent.slug,
            widget_token=request.widget.token,
            widget_session_id=str(request.widget_visitor_session.id),
            regenerate_message_id=data.get("regenerate_message_id"),
        )
        return JsonResponse({"task_id": task.id, "status": "accepted"}, status=202)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(widget_session_required, name="dispatch")
class ChatWidgetSocketAuthView(View):
    def get(self, request, token):
        if request.widget.token != token:
            return JsonResponse({"error": "Widget token mismatch"}, status=403)
        return JsonResponse(
            {
                "route_key": f"widget_session:{request.widget_visitor_session.id}",
                "session_id": str(request.widget_visitor_session.id),
            },
            status=200,
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ChatWidgetView(View):
    """View para gestionar Chat Widgets (CRUD)."""
    
    def _get_user_organization(self, user):
        """Get user's organization (owner or member)."""
        if not user:
            return None
        owned_org = Organization.objects.filter(owner=user).first()
        if owned_org:
            return owned_org
        if hasattr(user, 'profile') and user.profile.organization:
            return user.profile.organization
        return None

    def _check_permission(self, user, organization):
        """Check if user has permission to manage chat widgets."""
        if not organization:
            raise PermissionDenied("User has no organization.")
        enabled, _ = FeatureFlagService.is_feature_enabled(
            "chat-widgets-management", organization=organization, user=user
        )
        if not enabled:
            raise PermissionDenied("You are not allowed to manage chat widgets. The 'chat-widgets-management' feature flag is not enabled for your organization.")

    def _get_user_agents(self, user):
        """Get agents that belong to the user or their organization."""
        from api.ai_layers.models import Agent
        from django.db.models import Q
        
        user_org = None
        if hasattr(user, 'profile') and user.profile.organization:
            user_org = user.profile.organization
        
        if user_org:
            return Agent.objects.filter(Q(user=user) | Q(organization=user_org))
        return Agent.objects.filter(user=user)
    
    def get(self, request, *args, **kwargs):
        """Get all widgets for user or a single widget by ID."""
        user = request.user
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        widget_id = kwargs.get("id")
        
        if widget_id:
            # Get single widget
            try:
                widget = ChatWidget.objects.get(id=widget_id, created_by=user)
                serializer = ChatWidgetSerializer(widget, context={'request': request})
                return JsonResponse(serializer.data, safe=False)
            except ChatWidget.DoesNotExist:
                return JsonResponse(
                    {"message": "Widget not found", "status": 404}, status=404
                )
        else:
            # Get all widgets for the user
            widgets = ChatWidget.objects.filter(created_by=user).order_by("-created_at")
            serializer = ChatWidgetSerializer(widgets, many=True, context={'request': request})
            return JsonResponse(serializer.data, safe=False)
    
    def post(self, request, *args, **kwargs):
        """Create a new widget."""
        user = request.user
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Invalid JSON", "status": 400}, status=400
            )
        
        # Validate that agent belongs to user
        agent_id = data.get("agent_id")
        if agent_id:
            user_agents = self._get_user_agents(user)
            if not user_agents.filter(id=agent_id).exists():
                return JsonResponse(
                    {"message": "Agent not found or not accessible", "status": 403},
                    status=403
                )
        
        serializer = ChatWidgetSerializer(data=data, context={'request': request})
        if serializer.is_valid():
            serializer.save(created_by=user)
            return JsonResponse(serializer.data, status=201)
        else:
            return JsonResponse(
                {"message": "Validation error", "errors": serializer.errors, "status": 400},
                status=400
            )
    
    def put(self, request, *args, **kwargs):
        """Update an existing widget."""
        user = request.user
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        widget_id = kwargs.get("id")
        
        if not widget_id:
            return JsonResponse(
                {"message": "Widget ID is required", "status": 400}, status=400
            )
        
        try:
            widget = ChatWidget.objects.get(id=widget_id, created_by=user)
        except ChatWidget.DoesNotExist:
            return JsonResponse(
                {"message": "Widget not found", "status": 404}, status=404
            )
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Invalid JSON", "status": 400}, status=400
            )
        
        # Validate that agent belongs to user if being changed
        agent_id = data.get("agent_id")
        if agent_id:
            user_agents = self._get_user_agents(user)
            if not user_agents.filter(id=agent_id).exists():
                return JsonResponse(
                    {"message": "Agent not found or not accessible", "status": 403},
                    status=403
                )
        
        serializer = ChatWidgetSerializer(widget, data=data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, safe=False)
        else:
            return JsonResponse(
                {"message": "Validation error", "errors": serializer.errors, "status": 400},
                status=400
            )
    
    def delete(self, request, *args, **kwargs):
        """Delete a widget."""
        user = request.user
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        widget_id = kwargs.get("id")
        
        if not widget_id:
            return JsonResponse(
                {"message": "Widget ID is required", "status": 400}, status=400
            )
        
        try:
            widget = ChatWidget.objects.get(id=widget_id, created_by=user)
            widget.delete()
            return JsonResponse(
                {"message": "Widget deleted successfully", "status": 200},
                status=200
            )
        except ChatWidget.DoesNotExist:
            return JsonResponse(
                {"message": "Widget not found", "status": 404}, status=404
            )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ConversationAlertView(View):
    def _get_user_organizations(self, user):
        """Get all organizations where user is owner or member."""
        owned_orgs = Organization.objects.filter(owner=user)
        member_orgs = Organization.objects.none()
        if hasattr(user, 'profile') and user.profile.organization:
            member_orgs = Organization.objects.filter(id=user.profile.organization.id)
        return (owned_orgs | member_orgs).distinct()
    
    def get(self, request, *args, **kwargs):
        user = request.user
        alert_id = kwargs.get("id")
        
        user_organizations = self._get_user_organizations(user)
        
        if alert_id:
            # Get single alert
            try:
                alert = ConversationAlert.objects.get(
                    id=alert_id,
                    alert_rule__organization__in=user_organizations
                )
                serializer = ConversationAlertSerializer(alert, context={'request': request})
                return JsonResponse(serializer.data, safe=False)
            except ConversationAlert.DoesNotExist:
                return JsonResponse(
                    {"message": "Alert not found", "status": 404}, status=404
                )
        else:
            # Get all alerts filtered by status
            status_filter = request.GET.get("status", "all")
            
            # Get alerts from user's organizations
            alerts = ConversationAlert.objects.filter(
                alert_rule__organization__in=user_organizations
            )
            
            if status_filter != "all":
                alerts = alerts.filter(status=status_filter.upper())
            
            alerts = alerts.order_by("-created_at")
            serializer = ConversationAlertSerializer(alerts, many=True, context={'request': request})
            return JsonResponse(serializer.data, safe=False)

    def put(self, request, *args, **kwargs):
        user = request.user
        alert_id = kwargs.get("id")
        data = json.loads(request.body)
        
        if not alert_id:
            return JsonResponse(
                {"message": "Alert ID is required", "status": 400}, status=400
            )
        
        user_organizations = self._get_user_organizations(user)
        
        try:
            alert = ConversationAlert.objects.get(
                id=alert_id,
                alert_rule__organization__in=user_organizations
            )
        except ConversationAlert.DoesNotExist:
            return JsonResponse(
                {"message": "Alert not found", "status": 404}, status=404
            )
        
        # Update status
        new_status = data.get("status")
        if new_status:
            if new_status.upper() not in ["PENDING", "NOTIFIED", "RESOLVED", "DISMISSED"]:
                return JsonResponse(
                    {"message": "Invalid status", "status": 400}, status=400
                )
            alert.status = new_status.upper()
            
            # Set resolved_by or dismissed_by based on status
            if new_status.upper() == "RESOLVED":
                alert.resolved_by = user
                alert.dismissed_by = None
            elif new_status.upper() == "DISMISSED":
                alert.dismissed_by = user
                alert.resolved_by = None
            
            alert.save()
        
        serializer = ConversationAlertSerializer(alert, context={'request': request})
        return JsonResponse(serializer.data, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ConversationAlertStatsView(View):
    def get(self, request):
        user = request.user
        
        # Get user's organizations
        owned_orgs = Organization.objects.filter(owner=user)
        # Get organization from user profile
        member_orgs = Organization.objects.none()
        if hasattr(user, 'profile') and user.profile.organization:
            member_orgs = Organization.objects.filter(id=user.profile.organization.id)
        user_organizations = (owned_orgs | member_orgs).distinct()
        
        # Get alerts from user's organizations
        alerts = ConversationAlert.objects.filter(
            alert_rule__organization__in=user_organizations
        )
        
        stats = {
            "total": alerts.count(),
            "pending": alerts.filter(status="PENDING").count(),
            "notified": alerts.filter(status="NOTIFIED").count(),
            "resolved": alerts.filter(status="RESOLVED").count(),
            "dismissed": alerts.filter(status="DISMISSED").count(),
        }
        
        return JsonResponse(stats, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ConversationAlertRuleView(View):
    """View para gestionar Alert Rules (CRUD) con verificación de feature flag."""
    
    def _get_user_organization(self, user):
        """Get user's organization (owner or member)."""
        if not user:
            return None
        
        # Buscar si el usuario es owner de alguna organización
        owned_org = Organization.objects.filter(owner=user).first()
        if owned_org:
            return owned_org
        
        # Buscar si el usuario tiene una organización en su perfil
        if hasattr(user, 'profile') and user.profile.organization:
            return user.profile.organization
        
        return None
    
    def _check_permission(self, user, organization):
        """Check if user has permission to manage alert rules."""
        if not organization:
            raise PermissionDenied("User has no organization.")
        
        enabled, _ = FeatureFlagService.is_feature_enabled(
            "alert-rules-manager", organization=organization, user=user
        )
        if not enabled:
            raise PermissionDenied("You are not allowed to manage alert rules. The 'alert-rules-manager' feature flag is not enabled for your organization.")
    
    def get(self, request, *args, **kwargs):
        """Get all alert rules for user's organization."""
        user = request.user
        rule_id = kwargs.get("id")
        
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        if rule_id:
            # Get single alert rule
            try:
                rule = ConversationAlertRule.objects.get(
                    id=rule_id,
                    organization=organization
                )
                serializer = ConversationAlertRuleSerializer(rule)
                return JsonResponse(serializer.data, safe=False)
            except ConversationAlertRule.DoesNotExist:
                return JsonResponse(
                    {"message": "Alert rule not found", "status": 404}, 
                    status=404
                )
        else:
            # Get all alert rules for the organization (enabled and disabled)
            rules = ConversationAlertRule.objects.filter(
                organization=organization
            ).order_by("-created_at")
            serializer = ConversationAlertRuleSerializer(rules, many=True)
            return JsonResponse(serializer.data, safe=False)
    
    def post(self, request, *args, **kwargs):
        """Create a new alert rule."""
        user = request.user
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Invalid JSON", "status": 400}, 
                status=400
            )
        
        # Set organization and created_by
        serializer = ConversationAlertRuleSerializer(data=data)
        if serializer.is_valid():
            serializer.save(organization=organization, created_by=user)
            # Auto-enable conversation-analysis when the first alert rule is created
            FeatureFlagService.ensure_feature_enabled("conversation-analysis", organization)
            return JsonResponse(serializer.data, status=201)
        else:
            return JsonResponse(
                {"message": "Validation error", "errors": serializer.errors, "status": 400},
                status=400
            )
    
    def put(self, request, *args, **kwargs):
        """Update an existing alert rule."""
        user = request.user
        rule_id = kwargs.get("id")
        
        if not rule_id:
            return JsonResponse(
                {"message": "Alert rule ID is required", "status": 400}, 
                status=400
            )
        
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        try:
            rule = ConversationAlertRule.objects.get(
                id=rule_id,
                organization=organization
            )
        except ConversationAlertRule.DoesNotExist:
            return JsonResponse(
                {"message": "Alert rule not found", "status": 404}, 
                status=404
            )
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Invalid JSON", "status": 400}, 
                status=400
            )
        
        # Don't allow changing organization or created_by
        data.pop("organization", None)
        data.pop("created_by", None)
        
        serializer = ConversationAlertRuleSerializer(rule, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, safe=False)
        else:
            return JsonResponse(
                {"message": "Validation error", "errors": serializer.errors, "status": 400},
                status=400
            )
    
    def delete(self, request, *args, **kwargs):
        """Delete an alert rule."""
        user = request.user
        rule_id = kwargs.get("id")
        
        if not rule_id:
            return JsonResponse(
                {"message": "Alert rule ID is required", "status": 400}, 
                status=400
            )
        
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        try:
            rule = ConversationAlertRule.objects.get(
                id=rule_id,
                organization=organization
            )
            rule.delete()
            return JsonResponse(
                {"message": "Alert rule deleted successfully", "status": 200},
                status=200
            )
        except ConversationAlertRule.DoesNotExist:
            return JsonResponse(
                {"message": "Alert rule not found", "status": 404}, 
                status=404
            )
@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class TagView(View):
    """View para gestionar Tags (CRUD) con verificación de feature flag."""
    
    def _get_user_organization(self, user):
        """Get user's organization (owner or member)."""
        if not user:
            return None
        
        # Buscar si el usuario es owner de alguna organización
        owned_org = Organization.objects.filter(owner=user).first()
        if owned_org:
            return owned_org
        
        # Buscar si el usuario tiene una organización en su perfil
        if hasattr(user, 'profile') and user.profile.organization:
            return user.profile.organization
        
        return None
    
    def _check_permission(self, user, organization):
        """Check if user has permission to manage tags."""
        if not organization:
            raise PermissionDenied("User has no organization.")
        
        enabled, _ = FeatureFlagService.is_feature_enabled(
            "tags-management", organization=organization, user=user
        )
        if not enabled:
            raise PermissionDenied("You are not allowed to manage tags. The 'tags-management' feature flag is not enabled for your organization.")
    
    def get(self, request, *args, **kwargs):
        """Get all tags for user's organization."""
        user = request.user
        tag_id = kwargs.get("id")
        
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        if tag_id:
            # Get single tag
            try:
                tag = Tag.objects.get(
                    id=tag_id,
                    organization=organization
                )
                serializer = TagSerializer(tag)
                return JsonResponse(serializer.data, safe=False)
            except Tag.DoesNotExist:
                return JsonResponse(
                    {"message": "Tag not found", "status": 404}, 
                    status=404
                )
        else:
            # Get all tags for the organization
            tags = Tag.objects.filter(
                organization=organization
            ).order_by("title")
            serializer = TagSerializer(tags, many=True)
            return JsonResponse(serializer.data, safe=False)
    
    def post(self, request, *args, **kwargs):
        """Create a new tag."""
        user = request.user
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Invalid JSON", "status": 400}, 
                status=400
            )
        
        # Set organization
        serializer = TagSerializer(data=data)
        if serializer.is_valid():
            serializer.save(organization=organization)
            # Auto-enable conversation-analysis when the first tag is created
            FeatureFlagService.ensure_feature_enabled("conversation-analysis", organization)
            return JsonResponse(serializer.data, status=201)
        else:
            return JsonResponse(
                {"message": "Validation error", "errors": serializer.errors, "status": 400},
                status=400
            )
    
    def put(self, request, *args, **kwargs):
        """Update an existing tag."""
        user = request.user
        tag_id = kwargs.get("id")
        
        if not tag_id:
            return JsonResponse(
                {"message": "Tag ID is required", "status": 400}, 
                status=400
            )
        
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        try:
            tag = Tag.objects.get(
                id=tag_id,
                organization=organization
            )
        except Tag.DoesNotExist:
            return JsonResponse(
                {"message": "Tag not found", "status": 404}, 
                status=404
            )
        
        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse(
                {"message": "Invalid JSON", "status": 400}, 
                status=400
            )
        
        # Don't allow changing organization
        data.pop("organization", None)
        
        serializer = TagSerializer(tag, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, safe=False)
        else:
            return JsonResponse(
                {"message": "Validation error", "errors": serializer.errors, "status": 400},
                status=400
            )
    
    def delete(self, request, *args, **kwargs):
        """Delete a tag."""
        user = request.user
        tag_id = kwargs.get("id")
        
        if not tag_id:
            return JsonResponse(
                {"message": "Tag ID is required", "status": 400}, 
                status=400
            )
        
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)
        
        try:
            tag = Tag.objects.get(
                id=tag_id,
                organization=organization
            )
            tag.delete()
            return JsonResponse(
                {"message": "Tag deleted successfully", "status": 200},
                status=200
            )
        except Tag.DoesNotExist:
            return JsonResponse(
                {"message": "Tag not found", "status": 404}, 
                status=404
            )

