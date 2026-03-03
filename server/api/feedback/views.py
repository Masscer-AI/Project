import json
from api.authenticate.decorators.token_required import token_required
from .serializers import ReactionSerializer, ReactionTemplateSerializer
from rest_framework import status
from .models import ReactionTemplate
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from .models import Reaction
from api.messaging.models import Message

# Import django view to use View instead of APIView
from django.views import View

from api.utils.color_printer import printer
from django.core.cache import cache


@method_decorator(token_required, name="get")
@method_decorator(csrf_exempt, name="dispatch")
class ReactionTemplateView(View):
    # TIMEOUT DE UNA SEMANA YA QUE ESTOS DATOS SON LOS MISMOS PARA TODOS LOS USUARIOS
    CACHE_TIMEOUT = 604800

    def get(self, request):
        cache_key = "reaction_templates"
        cached_data = cache.get(cache_key)
        if cached_data:
            return JsonResponse(cached_data, status=status.HTTP_200_OK, safe=False)
        reaction_templates = ReactionTemplate.objects.filter(type="system")
        serializer = ReactionTemplateSerializer(reaction_templates, many=True)
        cache.set(cache_key, serializer.data, timeout=self.CACHE_TIMEOUT)
        printer.info("Updated cache")
        return JsonResponse(serializer.data, status=status.HTTP_200_OK, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class ReactionView(View):
    def post(self, request):
        data = json.loads(request.body)
        printer.blue(data)
        user = request.user
        conversation_id = data.get("conversation")
        template_id = data.get("template")
        message_id = data.get("message")
        if not template_id or (not message_id and not conversation_id):
            printer.red("Missing required fields")
            return JsonResponse(
                {"error": "Missing required fields"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data["user"] = user.id
        if message_id:
            m = Message.objects.get(id=message_id)

            if Reaction.objects.filter(
                user=user, template=template_id, message=m
            ).exists():
                # Remove the reaction
                Reaction.objects.filter(
                    user=user, template=template_id, message=m
                ).delete()
                printer.green("Reaction removed")
                return JsonResponse(
                    {"message": "Reaction removed"}, status=status.HTTP_200_OK
                )

        serializer = ReactionSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            printer.green("Reaction created")
            return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)
        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
