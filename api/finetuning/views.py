import json
from django.shortcuts import get_object_or_404

from .serializers import CompletionSerializer
from .models import Completion

from rest_framework import status
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from api.authenticate.decorators.token_required import token_required
from django.http import JsonResponse

# from api.utils.color_printer import printer
from rest_framework.permissions import AllowAny
from django.views import View
from .actions import create_training_generator, get_user_completions


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class GenerateTrainingDataView(View):
    def post(self, request):
        data = json.loads(request.body)

        create_training_generator(data, request.user)

        return JsonResponse(
            {"message": "Generating completions"},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class CompletionsView(View):
    permission_classes = [AllowAny]

    def get(self, request):
        completions = get_user_completions(request.user)
        return JsonResponse(completions, status=status.HTTP_200_OK, safe=False)

    def put(self, request, completion_id):
        data = json.loads(request.body)
        completion = get_object_or_404(Completion, id=completion_id)

        serializer = CompletionSerializer(completion, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                {"message": "Completion updated"}, status=status.HTTP_200_OK
            )
        return JsonResponse(
            {"message": "Invalid data"}, status=status.HTTP_400_BAD_REQUEST
        )

    def delete(self, request, completion_id):
        completion = get_object_or_404(Completion, id=completion_id)
        completion.remove_from_memory()
        completion.delete()
        return JsonResponse(
            {"message": "Completion deleted"}, status=status.HTTP_200_OK
        )
