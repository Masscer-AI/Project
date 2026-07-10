import json
import logging

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from api.authenticate.decorators.token_required import token_required
from api.messaging.tasks import get_user_organization

from .access import get_voice_by_id, resolve_accessible_voices
from .preview import get_or_create_voice_preview_url
from .serializers import VoiceSerializer

logger = logging.getLogger(__name__)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class VoiceListView(View):
    def get(self, request):
        organization = get_user_organization(request.user)
        voices = resolve_accessible_voices(user=request.user, organization=organization)
        data = VoiceSerializer(voices, many=True).data
        return JsonResponse(data, status=status.HTTP_200_OK, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class VoicePreviewView(View):
    def post(self, request):
        try:
            data = json.loads(request.body or "{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON body."}, status=400)

        voice_id = (data.get("voice_id") or "").strip()
        if not voice_id:
            return JsonResponse({"error": "voice_id is required."}, status=400)

        organization = get_user_organization(request.user)
        try:
            voice = get_voice_by_id(
                voice_id,
                user=request.user,
                organization=organization,
            )
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)

        try:
            url = get_or_create_voice_preview_url(voice=voice)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        except Exception:
            logger.exception("VoicePreviewView failed for voice_id=%s", voice_id)
            return JsonResponse(
                {"error": "Could not generate voice preview."},
                status=400,
            )

        return JsonResponse(
            {"voice_id": str(voice.id), "url": url},
            status=status.HTTP_200_OK,
        )
