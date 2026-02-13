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
from api.authenticate.models import Organization
from api.authenticate.services import FeatureFlagService
from django.core.exceptions import PermissionDenied


def _check_train_agents_permission(user):
    """Check if user has the train-agents feature flag."""
    if not user:
        raise PermissionDenied("User has no organization.")
    owned_org = Organization.objects.filter(owner=user).first()
    organization = owned_org
    if not organization and hasattr(user, 'profile') and user.profile.organization:
        organization = user.profile.organization
    if not organization:
        raise PermissionDenied("User has no organization.")
    enabled, _ = FeatureFlagService.is_feature_enabled(
        "train-agents", organization=organization, user=user
    )
    if not enabled:
        raise PermissionDenied("You are not allowed to generate training data. The 'train-agents' feature flag is not enabled for your organization.")


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class GenerateTrainingDataView(View):
    def post(self, request):
        _check_train_agents_permission(request.user)
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

    def post(self, request):
        data = json.loads(request.body)
        
        prompt = data.get("prompt")
        answer = data.get("answer")
        agent_id = data.get("agent")
        approved = data.get("approved", False)
        
        if not prompt or not answer:
            return JsonResponse(
                {"message": "Prompt and answer are required"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        completion_data = {
            "prompt": prompt,
            "answer": answer,
            "approved": approved,
        }
        
        if agent_id:
            completion_data["agent"] = agent_id
        
        serializer = CompletionSerializer(data=completion_data)
        if serializer.is_valid():
            serializer.save()
            return JsonResponse(
                serializer.data,
                status=status.HTTP_201_CREATED
            )
        return JsonResponse(
            {"message": "Invalid data", "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

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




@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class BulkCompletionView(View):
    permission_classes = [AllowAny]

    def put(self, request):
        data = json.loads(request.body)
        completions_data = data

        if not completions_data:
            return JsonResponse(
                {"message": "No completions provided"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        updated_completions = []
        for completion_data in completions_data:
            completion_id = completion_data.get("id")
            print(completion_id, "COMPLETION ID")
            completion = get_object_or_404(Completion, id=completion_id)

            serializer = CompletionSerializer(completion, data=completion_data, partial=True)
            if serializer.is_valid():
                serializer.save()
                updated_completions.append(serializer.data)
            else:
                return JsonResponse(
                    {"message": "Invalid data for completion id: {}".format(completion_id)}, 
                    status=status.HTTP_400_BAD_REQUEST
                )

        return JsonResponse(
            {"message": "Completions updated", "updated_completions": updated_completions}, 
            status=status.HTTP_200_OK
        )

    def delete(self, request):
        data = json.loads(request.body)
        completions_ids = data.get("completions_ids", [])

        if not completions_ids:
            return JsonResponse(
                {"message": "No completion IDs provided"}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        deleted_ids = []
        for completion_id in completions_ids:
            completion = get_object_or_404(Completion, id=completion_id)
            completion.remove_from_memory()  
            completion.delete()
            deleted_ids.append(completion_id)

        return JsonResponse(
            {"message": "Completions deleted", "deleted_ids": deleted_ids}, 
            status=status.HTTP_200_OK
        )
