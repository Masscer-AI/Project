import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from api.authenticate.decorators.token_required import token_required
from .models import UserPreferences
from .serializers import UserPreferencesSerializer
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserPreferencesView(View):
    def get(self, request):

        user_preferences = UserPreferences.objects.filter(user=request.user).first()
        if user_preferences is None:
            # create a new UserPreferences object for the user
            user_preferences = UserPreferences(user=request.user)
            user_preferences.save()

        serializer = UserPreferencesSerializer(user_preferences)
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

    def put(self, request):

        user_preferences = UserPreferences.objects.filter(user=request.user).first()
        if user_preferences is None:
            user_preferences = UserPreferences(user=request.user)
            user_preferences.save()

        data = json.loads(request.body)
        
        serializer = UserPreferencesSerializer(user_preferences, data=data)

        if serializer.is_valid():
            serializer.save()
            return JsonResponse(serializer.data, status=status.HTTP_200_OK)

        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
