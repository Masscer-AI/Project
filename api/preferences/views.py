import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from api.authenticate.decorators.token_required import token_required
from .models import UserPreferences, UserTags, UserVoices, WebPage
from .serializers import UserPreferencesSerializer, WebPageSerializer
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


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserVoicesView(View):
    def get(self, request):
        user_voices = UserVoices.objects.filter(user=request.user).first()
        if user_voices is None:
            user_voices = UserVoices(user=request.user)
            user_voices.save()

        return JsonResponse(user_voices.voices, status=status.HTTP_200_OK, safe=False)

    def put(self, request):
        user_voices = UserVoices.objects.filter(user=request.user).first()
        new_voices = json.loads(request.body)
        if user_voices is None:
            user_voices = UserVoices(user=request.user, voices=new_voices)
            user_voices.save()
        else:
            user_voices.voices = new_voices
            user_voices.save()

        return JsonResponse(user_voices.voices, status=status.HTTP_200_OK, safe=False)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WebPagesView(View):
    def get(self, request):
        pinned = request.GET.get("pinned")
        pages = WebPage.objects.filter(user=request.user)
        if pinned in ["true", "1", "yes"]:
            pages = pages.filter(is_pinned=True)

        serializer = WebPageSerializer(pages, many=True)
        return JsonResponse(serializer.data, status=status.HTTP_200_OK, safe=False)

    def post(self, request):
        data = json.loads(request.body or "{}")
        url = (data.get("url") or "").strip()
        if not url:
            return JsonResponse({"error": "url-required"}, status=status.HTTP_400_BAD_REQUEST)

        title = data.get("title")
        is_pinned = data.get("is_pinned")

        page = WebPage.objects.filter(user=request.user, url=url).first()
        if page:
            if title is not None:
                page.title = title
            if is_pinned is not None:
                page.is_pinned = bool(is_pinned)
            page.save()
            serializer = WebPageSerializer(page)
            return JsonResponse(serializer.data, status=status.HTTP_200_OK)

        page = WebPage.objects.create(
            user=request.user,
            url=url,
            title=title or "",
            is_pinned=bool(is_pinned) if is_pinned is not None else False,
        )
        serializer = WebPageSerializer(page)
        return JsonResponse(serializer.data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class WebPageDetailView(View):
    def patch(self, request, page_id):
        page = WebPage.objects.filter(user=request.user, id=page_id).first()
        if not page:
            return JsonResponse({"error": "not-found"}, status=status.HTTP_404_NOT_FOUND)

        data = json.loads(request.body or "{}")
        if "url" in data:
            page.url = data["url"]
        if "title" in data:
            page.title = data["title"] or ""
        if "is_pinned" in data:
            page.is_pinned = bool(data["is_pinned"])
        page.save()

        serializer = WebPageSerializer(page)
        return JsonResponse(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, page_id):
        page = WebPage.objects.filter(user=request.user, id=page_id).first()
        if not page:
            return JsonResponse({"error": "not-found"}, status=status.HTTP_404_NOT_FOUND)

        page.delete()
        return JsonResponse({"deleted": True}, status=status.HTTP_200_OK)
