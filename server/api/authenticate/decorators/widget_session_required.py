from django.core import signing
from django.http import JsonResponse
from django.utils import timezone

from api.messaging.models import ChatWidget, WidgetVisitorSession


WIDGET_SESSION_TOKEN_MAX_AGE_SECONDS = 3600
WIDGET_SESSION_TOKEN_SALT = "widget-session-v1"


def create_widget_session_token(*, widget_token: str, session_id: str, visitor_id: str) -> str:
    return signing.dumps(
        {
            "widget_token": widget_token,
            "session_id": session_id,
            "visitor_id": visitor_id,
        },
        salt=WIDGET_SESSION_TOKEN_SALT,
    )


def decode_widget_session_token(token: str):
    return signing.loads(
        token,
        salt=WIDGET_SESSION_TOKEN_SALT,
        max_age=WIDGET_SESSION_TOKEN_MAX_AGE_SECONDS,
    )


def widget_session_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header:
            return JsonResponse({"error": "Widget session token missing"}, status=401)

        try:
            token_type, token_key = auth_header.split(" ", 1)
        except ValueError:
            return JsonResponse({"error": "Invalid token format"}, status=401)

        if token_type != "WidgetSession":
            return JsonResponse({"error": "Invalid token type"}, status=401)

        try:
            payload = decode_widget_session_token(token_key)
        except signing.SignatureExpired:
            return JsonResponse({"error": "Widget session expired"}, status=401)
        except signing.BadSignature:
            return JsonResponse({"error": "Invalid widget session token"}, status=401)

        widget_token = payload.get("widget_token")
        session_id = payload.get("session_id")
        visitor_id = payload.get("visitor_id")
        if not widget_token or not session_id or not visitor_id:
            return JsonResponse({"error": "Invalid widget session payload"}, status=401)

        try:
            widget = ChatWidget.objects.get(token=widget_token, enabled=True)
        except ChatWidget.DoesNotExist:
            return JsonResponse({"error": "Widget not found or disabled"}, status=404)

        try:
            session = WidgetVisitorSession.objects.get(
                id=session_id,
                widget=widget,
                visitor_id=visitor_id,
            )
        except WidgetVisitorSession.DoesNotExist:
            return JsonResponse({"error": "Widget session not found"}, status=401)

        if session.is_blocked:
            return JsonResponse({"error": "Widget session blocked"}, status=403)

        if session.expires_at < timezone.now():
            return JsonResponse({"error": "Widget session expired"}, status=401)

        session.last_seen_at = timezone.now()
        session.save(update_fields=["last_seen_at"])

        request.user = None
        request.widget = widget
        request.widget_visitor_session = session
        request.widget_session_claims = payload
        return view_func(request, *args, **kwargs)

    return _wrapped_view
