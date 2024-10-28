import json
# from .serializers import TrainingGeneratorSerializer

from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from api.authenticate.decorators.token_required import token_required
from django.http import JsonResponse
# from api.utils.color_printer import printer
from rest_framework.permissions import AllowAny
from django.views import View
from .actions import create_training_generator


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class GenerateTrainingDataView(View):
    permission_classes = [AllowAny]

    def post(self, request):
        data = json.loads(request.body)

        create_training_generator(data, request.user)

        return JsonResponse(
            {"message": "Generating completions"},
            status=status.HTTP_201_CREATED,
        )
