import json
from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied

from api.authenticate.models import Organization
from api.authenticate.decorators.token_required import token_required
from api.authenticate.services import FeatureFlagService
from api.notify.models import NotificationRule, UserNotification
from api.notify.serializers import NotificationRuleSerializer, UserNotificationSerializer

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
        # Organization owners can always manage notification rules; others need the flag.
        if organization.owner_id == user.id:
            return
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


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class UserNotificationView(View):
    """List and patch in-app notifications for the authenticated user only."""

    def _require_user(self, request):
        if request.user is None:
            return JsonResponse({"error": "Forbidden."}, status=403)
        return None

    def get(self, request, *args, **kwargs):
        err = self._require_user(request)
        if err:
            return err
        user = request.user
        notification_id = kwargs.get("id")

        qs = (
            UserNotification.objects.filter(target_user=user)
            .select_related("organization", "notification_rule", "alert")
            .order_by("-created_at")
        )

        if notification_id:
            try:
                obj = qs.get(id=notification_id)
            except UserNotification.DoesNotExist:
                return JsonResponse({"error": "Not found."}, status=404)
            return JsonResponse(UserNotificationSerializer(obj).data)

        unread = request.GET.get("unread", "").lower()
        if unread in ("1", "true", "yes"):
            qs = qs.filter(read_at__isnull=True)

        return JsonResponse(UserNotificationSerializer(qs, many=True).data, safe=False)

    def patch(self, request, *args, **kwargs):
        err = self._require_user(request)
        if err:
            return err
        user = request.user
        notification_id = kwargs.get("id")
        if not notification_id:
            return JsonResponse({"error": "Notification id required."}, status=400)

        try:
            body = json.loads(request.body or b"{}")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON."}, status=400)

        if body and body.get("read") is False:
            return JsonResponse(
                {"error": "Only marking as read is supported (read: true or omit)."},
                status=400,
            )

        try:
            obj = UserNotification.objects.select_related(
                "organization", "notification_rule", "alert"
            ).get(id=notification_id, target_user=user)
        except UserNotification.DoesNotExist:
            return JsonResponse({"error": "Not found."}, status=404)

        now = timezone.now()
        obj.read_at = now
        obj.ignored_at = None
        obj.expires_at = now + timedelta(days=30)
        obj.save(update_fields=["read_at", "ignored_at", "expires_at"])

        return JsonResponse(UserNotificationSerializer(obj).data)
