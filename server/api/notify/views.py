import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied

from api.authenticate.models import Organization, Role
from api.authenticate.decorators.token_required import token_required
from api.authenticate.services import FeatureFlagService
from api.notify.models import NotificationRule
from api.notify.serializers import NotificationRuleSerializer

FEATURE_FLAG = "can-set-notifications"


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class NotificationRuleView(View):

    def _get_user_organization(self, user):
        owned = Organization.objects.filter(owner=user).first()
        if owned:
            return owned
        if hasattr(user, "profile") and user.profile.organization:
            return user.profile.organization
        return None

    def _check_permission(self, user, organization):
        if not organization:
            raise PermissionDenied("User has no organization.")
        enabled, _ = FeatureFlagService.is_feature_enabled(
            FEATURE_FLAG, organization=organization, user=user
        )
        if not enabled:
            raise PermissionDenied(
                f"The '{FEATURE_FLAG}' feature flag is not enabled for your organization."
            )

    def get(self, request, *args, **kwargs):
        user = request.user
        rule_id = kwargs.get("id")
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)

        if rule_id:
            try:
                rule = NotificationRule.objects.get(id=rule_id, organization=organization)
            except NotificationRule.DoesNotExist:
                return JsonResponse({"error": "Not found."}, status=404)
            return JsonResponse(NotificationRuleSerializer(rule).data)

        rules = NotificationRule.objects.filter(organization=organization).order_by("-created_at")
        return JsonResponse(NotificationRuleSerializer(rules, many=True).data, safe=False)

    def post(self, request, *args, **kwargs):
        user = request.user
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=400)

        serializer = NotificationRuleSerializer(data=body)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        rule = serializer.save(organization=organization, created_by=user)
        return JsonResponse(NotificationRuleSerializer(rule).data, status=201)

    def put(self, request, *args, **kwargs):
        user = request.user
        rule_id = kwargs.get("id")
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)

        try:
            rule = NotificationRule.objects.get(id=rule_id, organization=organization)
        except NotificationRule.DoesNotExist:
            return JsonResponse({"error": "Not found."}, status=404)

        try:
            body = json.loads(request.body)
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=400)

        serializer = NotificationRuleSerializer(rule, data=body, partial=True)
        if not serializer.is_valid():
            return JsonResponse(serializer.errors, status=400)

        rule = serializer.save()
        return JsonResponse(NotificationRuleSerializer(rule).data)

    def delete(self, request, *args, **kwargs):
        user = request.user
        rule_id = kwargs.get("id")
        organization = self._get_user_organization(user)
        self._check_permission(user, organization)

        try:
            rule = NotificationRule.objects.get(id=rule_id, organization=organization)
        except NotificationRule.DoesNotExist:
            return JsonResponse({"error": "Not found."}, status=404)

        rule.delete()
        return JsonResponse({"message": "Deleted."}, status=200)
