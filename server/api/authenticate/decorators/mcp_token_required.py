from django.http import JsonResponse
from django.utils import timezone

from api.ai_layers.models import MCPClient


def _extract_bearer_key(request) -> str | None:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header:
        return None
    parts = auth_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def mcp_token_required(view_func):
    """Authenticate MCP gateway requests using a dedicated MCPClient Bearer key."""

    def _wrapped_view(request, *args, **kwargs):
        key = _extract_bearer_key(request)
        if not key:
            return JsonResponse({"error": "Bearer token missing"}, status=401)

        mcp_client = MCPClient.get_valid(key)
        if not mcp_client:
            return JsonResponse({"error": "Invalid or revoked MCP credential"}, status=401)

        profile = getattr(mcp_client.user, "profile", None)
        if profile and profile.organization_id and not profile.is_active:
            return JsonResponse(
                {"error": "Your account has been deactivated"},
                status=403,
            )

        MCPClient.objects.filter(pk=mcp_client.pk).update(last_used_at=timezone.now())

        request.user = mcp_client.user
        request.mcp_client = mcp_client
        return view_func(request, *args, **kwargs)

    return _wrapped_view
