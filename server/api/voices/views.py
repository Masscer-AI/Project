from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status

from api.authenticate.decorators.token_required import token_required
from api.messaging.tasks import get_user_organization

from .access import resolve_accessible_voices
from .serializers import VoiceSerializer


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class VoiceListView(View):
    def get(self, request):
        organization = get_user_organization(request.user)
        voices = resolve_accessible_voices(user=request.user, organization=organization)
        data = VoiceSerializer(voices, many=True).data
        return JsonResponse(data, status=status.HTTP_200_OK, safe=False)
