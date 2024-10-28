import os
import json
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from dotenv import load_dotenv
from .models import WSNumber, WSConversation
from api.utils.color_printer import printer
from .tasks import async_handle_webhook
from api.authenticate.decorators.token_required import token_required
from django.utils.decorators import method_decorator
from api.ai_layers.models import Agent

# import view
from rest_framework import generics
from .serializers import (
    WSNumberSerializer,
    WSConversationSerializer,
    BigWSConversationSerializer,
)


from django.views import View

load_dotenv()


@csrf_exempt
def webhook(request):
    if request.method == "POST":
        printer.blue("Receiving a webhook from Facebook")
        data = json.loads(request.body)
        printer.yellow(data)
        async_handle_webhook.delay(webhook_data=data)
        return HttpResponse(status=200)

    elif request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        # Check the mode and token sent are correct
        if mode == "subscribe" and token == os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN"):
            print("Webhook verified successfully!")
            return HttpResponse(challenge)
        else:
            return HttpResponse(status=403)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WSNumbersView(View):
    def get(self, request, *args, **kwargs):
        user = request.user
        ws_numbers = WSNumber.objects.filter(user=user)
        serializer = WSNumberSerializer(ws_numbers, many=True)
        return JsonResponse(serializer.data, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WSNumberDetailView(View):
    def put(self, request, *args, **kwargs):
        user = request.user
        number = kwargs.get("number")
        ws_number = WSNumber.objects.filter(user=user, number=number).first()

        if not ws_number:
            return JsonResponse({"error": "WSNumber not found"}, status=404)

        try:
            data = json.loads(request.body)
            agent_slug = data.get("slug")
            if agent_slug:
                agent = Agent.objects.filter(slug=agent_slug).first()
                if not agent:
                    return JsonResponse(
                        {"error": f"Agent with that slug {agent_slug} not found"},
                        status=404,
                    )

                ws_number.agent = agent
                ws_number.save()
                printer.success("WSNumber updated successfully")
                return JsonResponse(WSNumberSerializer(ws_number).data, status=200)

            name = data.get("name")
            if name:
                ws_number.name = name
                ws_number.save()
                printer.success("WSNumber updated successfully")
                return JsonResponse(WSNumberSerializer(ws_number).data, status=200)

            return JsonResponse({"error": "No agent slug provided"}, status=400)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
        except Exception as e:
            return JsonResponse({"error": str(e)}, status=500)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WSConversationsView(generics.ListCreateAPIView):
    serializer_class = WSConversationSerializer

    def get_queryset(self):
        user = self.request.user
        return WSConversation.objects.filter(ai_number__user=user)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WSConversationDetailView(View):
    def get(self, request, *args, **kwargs):
        printer.blue("Getting a conversation")
        user = request.user
        pk = kwargs.get("pk")
        conversation = WSConversation.objects.filter(
            ai_number__user=user, id=pk
        ).first()

        if not conversation:
            return JsonResponse({"error": "Conversation not found"}, status=404)

        # Serialize the conversation data
        serializer = BigWSConversationSerializer(conversation)
        return JsonResponse(serializer.data, status=200)

    def post(self, request, *args, **kwargs):
        printer.blue("Sending a message to a conversation")
        user = request.user
        pk = kwargs.get("pk")
        conversation = WSConversation.objects.filter(
            ai_number__user=user, id=pk
        ).first()

        body = json.loads(request.body)

        if not conversation:
            return JsonResponse({"error": "Conversation not found"}, status=404)

        message = body.get("message")
        if not message:
            return JsonResponse({"error": "No message provided"}, status=400)

        conversation.ai_number.send_message(conversation, message)

        # Here you would typically create a message object or perform any relevant action
        # For example:
        # conversation.messages.create(content=message, user=user)

        return JsonResponse({"message": "Message sent successfully"}, status=201)
