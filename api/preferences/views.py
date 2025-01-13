import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from api.authenticate.decorators.token_required import token_required
from .models import UserPreferences, UserTags
from .serializers import UserPreferencesSerializer
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt
from django.core.cache import cache
from api.utils.color_printer import printer


CACHE_TIMEOUT = 86400


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserPreferencesView(View):
    def get(self, request):
        # Generar una clave única para el caché basado en el usuario
        cache_key = f"user_preferences_{request.user.id}"
        cached_data = cache.get(cache_key)

        if cached_data:
            return JsonResponse(cached_data, status=status.HTTP_200_OK)

        # Si no hay datos en el caché, obtenerlos de la base de datos
        user_preferences = UserPreferences.objects.filter(user=request.user).first()
        if user_preferences is None:
            user_preferences = UserPreferences(user=request.user)
            user_preferences.save()

        serializer = UserPreferencesSerializer(user_preferences)
        response_data = serializer.data
        cache.set(cache_key, response_data, timeout=CACHE_TIMEOUT)

        return JsonResponse(response_data, status=status.HTTP_200_OK)

    def put(self, request):
        user_preferences = UserPreferences.objects.filter(user=request.user).first()
        if user_preferences is None:
            user_preferences = UserPreferences(user=request.user)
            user_preferences.save()

        # Parsear los datos enviados en el cuerpo de la solicitud
        data = json.loads(request.body)

        # Serializar y validar los datos
        serializer = UserPreferencesSerializer(user_preferences, data=data)

        if serializer.is_valid():
            serializer.save()

            cache_key = f"user_preferences_{request.user.id}"
            response_data = serializer.data
            cache.set(cache_key, response_data, timeout=CACHE_TIMEOUT)
            printer.info(f"Updated cache for user {request.user.id}")

            return JsonResponse(response_data, status=status.HTTP_200_OK)

        return JsonResponse(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserTagsView(View):
    def get(self, request):
        user_tags = UserTags.objects.filter(user=request.user).first()
        if user_tags is None:
            user_tags = UserTags(user=request.user)
            user_tags.save()

        return JsonResponse(user_tags.tags, status=status.HTTP_200_OK, safe=False)
