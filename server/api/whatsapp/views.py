import json
import os

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views import View
from django.utils.decorators import method_decorator
from dotenv import load_dotenv
from rest_framework import serializers

from api.ai_layers.access import accessible_agents_qs
from api.ai_layers.models import Agent
from api.authenticate.decorators.token_required import token_required
from api.authenticate.models import Organization
from api.authenticate.services import FeatureFlagService
from api.messaging.models import Conversation
from api.messaging.serializers import BigConversationSerializer, ConversationSerializer
from api.utils.color_printer import printer

from .capabilities_validation import validate_whatsapp_capabilities_list
from .conversations import whatsapp_conversation_visible_q, ws_number_visible_q
from .models import WSNumber
from .serializers import WSNumberSerializer
from .tasks import async_handle_webhook
from .webhook_signature import verify_meta_webhook_signature

load_dotenv()


def _whatsapp_get_user_organization(user):
    """Same resolution as ChatWidgetView (owned org first, then profile)."""
    if not user:
        return None
    owned_org = Organization.objects.filter(owner=user).first()
    if owned_org:
        return owned_org
    if hasattr(user, "profile") and user.profile.organization:
        return user.profile.organization
    return None


def _require_whatsapp_numbers_management(user):
    """
    End users customize lines (agent, capabilities, display name) only when this
    flag is on; provisioning stays in Django admin.
    """
    if not user or not user.is_authenticated:
        raise PermissionDenied("Authentication required.")
    organization = _whatsapp_get_user_organization(user)
    if not organization:
        raise PermissionDenied("User has no organization.")
    enabled, _ = FeatureFlagService.is_feature_enabled(
        "whatsapp-numbers-management", organization=organization, user=user
    )
    if not enabled:
        raise PermissionDenied(
            "WhatsApp number customization is not enabled. "
            "The 'whatsapp-numbers-management' feature flag must be on for your organization."
        )


@csrf_exempt
def webhook(request):
    if request.method == "POST":
        printer.blue("Receiving a webhook from Facebook")
        raw = request.body
        secret = getattr(settings, "WHATSAPP_APP_SECRET", "") or ""
        if secret:
            sig = request.META.get("HTTP_X_HUB_SIGNATURE_256", "")
            if not verify_meta_webhook_signature(raw, sig, secret):
                return HttpResponse(status=403)
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return HttpResponse(status=400)
        printer.yellow(data)
        async_handle_webhook.delay(webhook_data=data)
        return HttpResponse(status=200)

    elif request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        verify = getattr(settings, "WHATSAPP_WEBHOOK_VERIFY_TOKEN", "") or os.getenv(
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN", ""
        )
        if mode == "subscribe" and verify and token == verify:
            print("Webhook verified successfully!")
            return HttpResponse(challenge)
        else:
            return HttpResponse(status=403)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WSNumbersView(View):
    def get(self, request, *args, **kwargs):
        user = request.user
        _require_whatsapp_numbers_management(user)
        ws_numbers = WSNumber.objects.filter(ws_number_visible_q(user)).distinct()
        serializer = WSNumberSerializer(ws_numbers, many=True)
        return JsonResponse(serializer.data, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WSNumberDetailView(View):
    def put(self, request, *args, **kwargs):
        user = request.user
        _require_whatsapp_numbers_management(user)
        number = kwargs.get("number")
        ws_number = WSNumber.objects.filter(ws_number_visible_q(user), number=number).first()

        if not ws_number:
            return JsonResponse({"error": "WSNumber not found"}, status=404)

        try:
            data = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        updated = False

        agent_slug = data.get("slug")
        if agent_slug:
            agent = Agent.objects.filter(slug=agent_slug).first()
            if not agent:
                return JsonResponse(
                    {"error": f"Agent with that slug {agent_slug} not found"},
                    status=404,
                )
            if not accessible_agents_qs(user).filter(pk=agent.pk).exists():
                return JsonResponse(
                    {"error": "Agent not found or not accessible"},
                    status=403,
                )
            ws_number.agent = agent
            updated = True

        name = data.get("name")
        if name is not None:
            ws_number.name = name
            updated = True

        if "capabilities" in data:
            caps = data.get("capabilities")
            if caps is not None and not isinstance(caps, list):
                return JsonResponse(
                    {"error": "capabilities must be a list or null"},
                    status=400,
                )
            try:
                ws_number.capabilities = validate_whatsapp_capabilities_list(
                    caps if caps is not None else []
                )
            except serializers.ValidationError as exc:
                return JsonResponse(
                    {"error": "Invalid capabilities", "details": exc.detail},
                    status=400,
                )
            updated = True

        if updated:
            ws_number.save()
            printer.success("WSNumber updated successfully")
            return JsonResponse(WSNumberSerializer(ws_number).data, status=200)

        return JsonResponse({"error": "No recognized fields to update"}, status=400)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WSConversationsView(View):
    def get(self, request, *args, **kwargs):
        user = request.user
        _require_whatsapp_numbers_management(user)
        qs = (
            Conversation.objects.filter(whatsapp_conversation_visible_q(user))
            .exclude(ws_number__isnull=True)
            .order_by("-updated_at")
        )
        serializer = ConversationSerializer(qs, many=True, context={"request": request})
        return JsonResponse(serializer.data, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WSConversationDetailView(View):
    def get(self, request, *args, **kwargs):
        printer.blue("Getting a conversation")
        user = request.user
        _require_whatsapp_numbers_management(user)
        pk = kwargs.get("pk")
        conversation = (
            Conversation.objects.filter(whatsapp_conversation_visible_q(user), id=pk)
            .exclude(ws_number__isnull=True)
            .first()
        )

        if not conversation:
            return JsonResponse({"error": "Conversation not found"}, status=404)

        serializer = BigConversationSerializer(conversation, context={"request": request})
        return JsonResponse(serializer.data, status=200)

    def post(self, request, *args, **kwargs):
        printer.blue("Sending a message to a conversation")
        user = request.user
        _require_whatsapp_numbers_management(user)
        pk = kwargs.get("pk")
        conversation = (
            Conversation.objects.filter(whatsapp_conversation_visible_q(user), id=pk)
            .exclude(ws_number__isnull=True)
            .first()
        )

        if not conversation:
            return JsonResponse({"error": "Conversation not found"}, status=404)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        message = body.get("message")
        if not message:
            return JsonResponse({"error": "No message provided"}, status=400)

        conversation.ws_number.send_message(conversation, message)

        return JsonResponse({"message": "Message sent successfully"}, status=201)
