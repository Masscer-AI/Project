from django.http import JsonResponse
from ..models import Token, PublishableToken
from api.utils.color_printer import printer


def token_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return JsonResponse({"error": "Token missing"}, status=401)

        # Split the header to get the token key
        try:
            token_type, token_key = auth_header.split(" ")
        except ValueError:
            return JsonResponse({"error": "Invalid token format"}, status=401)

        # Try to validate as Token first
        token = Token.get_valid(token_key)
        if token:
            request.user = token.user
            # Block deactivated users from accessing any resource
            profile = getattr(token.user, "profile", None)
            if profile and profile.organization_id and not profile.is_active:
                return JsonResponse(
                    {"error": "Your account has been deactivated"},
                    status=403,
                )
        else:
            token = PublishableToken.get_valid(token_key)
            if token:
                request.user = None
            else:
                printer.error("Invalid or expired token")
                return JsonResponse({"error": "Invalid or expired token"}, status=401)

        # printer.success("Token is valid!")
        return view_func(request, *args, **kwargs)

    return _wrapped_view
