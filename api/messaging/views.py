from datetime import timedelta
from django.utils import timezone

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views import View
from .models import (
    Conversation,
    Message,
    MessageAttachment,
    SharedConversation,
    ChatWidget,
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
from .actions import transcribe_audio, complete_message
from django.core.files.storage import FileSystemStorage
import os
import uuid
from django.conf import settings


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
    user = request.user
    if conversation.user_id == user.id:
        return conversation, None
    org_user_ids = _get_org_user_ids(user)
    if org_user_ids and (
        conversation.user_id in org_user_ids or conversation.user_id is None
    ):
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
            scope = request.GET.get("scope", "org")
            if scope == "personal":
                conversations = Conversation.objects.filter(user=user).order_by(
                    "-created_at"
                )
            else:
                org_user_ids = _get_org_user_ids(user)
                if org_user_ids:
                    from django.db.models import Q

                    conversations = (
                        Conversation.objects.filter(
                            Q(user_id__in=org_user_ids) | Q(user__isnull=True)
                        )
                        .order_by("-created_at")
                    )
                else:
                    conversations = Conversation.objects.filter(user=user).order_by(
                        "-created_at"
                    )

            serialized_conversations = ConversationSerializer(
                conversations, many=True, context={"request": request}
            ).data
            return JsonResponse(serialized_conversations, safe=False)

    def post(self, request, *args, **kwargs):
        user = request.user

        existing_conversation = Conversation.objects.filter(
            user=user, messages__isnull=True
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
        conversation.delete()
        return JsonResponse({"status": "deleted"})


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
        else:
            content_type = "application/octet-stream"
        attachment = MessageAttachment.objects.create(
            conversation=conv,
            user=request.user,
            file=file_obj,
            content_type=content_type,
        )
        url = request.build_absolute_uri(attachment.file.url)
        result.append({"id": str(attachment.id), "url": url})

    return JsonResponse({"attachments": result})


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
class ChatWidgetAuthTokenView(View):
    def get(self, request, token):
        try:
            widget = ChatWidget.objects.get(token=token, enabled=True)
        except ChatWidget.DoesNotExist:
            return JsonResponse(
                {"error": "Widget not found or disabled", "status": 404}, status=404
            )

        # Get or create a Token for the widget's owner
        # Widgets need to authenticate as a user to access agents and other resources
        from api.authenticate.models import Token
        
        if not widget.created_by:
            return JsonResponse(
                {"error": "Widget has no owner configured", "status": 400}, status=400
            )

        # Get or create a token for the widget owner
        # Use a permanent token type so it doesn't expire
        auth_token, created = Token.get_or_create(
            user=widget.created_by,
            token_type="permanent"
        )

        return JsonResponse(
            {"token": auth_token.key, "token_type": "Token"},
            safe=False,
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

