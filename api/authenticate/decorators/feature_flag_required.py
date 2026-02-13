from functools import wraps
from django.http import JsonResponse
from api.authenticate.models import Organization
from api.authenticate.services import FeatureFlagService


def _get_user_organization(user):
    """Get user's organization (owner or member)."""
    if not user:
        return None
    owned_org = Organization.objects.filter(owner=user).first()
    if owned_org:
        return owned_org
    if hasattr(user, 'profile') and user.profile.organization:
        return user.profile.organization
    return None


def feature_flag_required(flag_name):
    """
    Decorator factory that checks a feature flag before allowing access.
    Must be applied AFTER token_required (i.e. below it in the decorator stack)
    so that request.user is already set.

    Usage with class-based views:
        @method_decorator(csrf_exempt, name="dispatch")
        @method_decorator(token_required, name="dispatch")
        @method_decorator(feature_flag_required("my-flag"), name="dispatch")
        class MyView(View):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            user = getattr(request, 'user', None)
            if not user:
                return JsonResponse(
                    {"error": f"Authentication required to access '{flag_name}' feature."},
                    status=401,
                )
            organization = _get_user_organization(user)
            if not organization:
                return JsonResponse(
                    {"error": "User has no organization."},
                    status=403,
                )
            enabled, _ = FeatureFlagService.is_feature_enabled(flag_name, organization=organization, user=user)
            if not enabled:
                return JsonResponse(
                    {"error": f"The '{flag_name}' feature is not enabled for your organization."},
                    status=403,
                )
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
