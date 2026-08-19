from django.http import JsonResponse


def error_response(exc: Exception, status: int = 400) -> JsonResponse:
    return JsonResponse({"error": str(exc)}, status=status)
