import json
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

from api.authenticate.decorators.token_required import token_required
from api.authenticate.models import Organization
from api.payments.models import Subscription
from api.consumption.models import OrganizationWallet


@method_decorator(csrf_exempt, name="dispatch")
@method_decorator(token_required, name="dispatch")
class OrganizationBillingView(View):
    def get(self, request, organization_id, *args, **kwargs):
        try:
            org = Organization.objects.get(id=organization_id)
        except Organization.DoesNotExist:
            return JsonResponse({"error": "Organization not found"}, status=404)

        if org.owner != request.user:
            return JsonResponse({"error": "Forbidden"}, status=403)

        subscription = (
            Subscription.objects.select_related("plan")
            .filter(organization=org)
            .order_by("-created_at")
            .first()
        )

        wallet = OrganizationWallet.objects.select_related("unit").filter(organization=org).first()

        subscription_data = None
        if subscription:
            subscription_data = {
                "id": str(subscription.id),
                "status": subscription.status,
                "payment_method": subscription.payment_method,
                "is_active": subscription.is_active(),
                "start_date": subscription.start_date.isoformat() if subscription.start_date else None,
                "end_date": subscription.end_date.isoformat() if subscription.end_date else None,
                "plan": {
                    "slug": subscription.plan.slug,
                    "display_name": subscription.plan.display_name,
                    "monthly_price_usd": str(subscription.plan.monthly_price_usd),
                    "credits_limit_usd": str(subscription.plan.credits_limit_usd) if subscription.plan.credits_limit_usd is not None else None,
                    "duration_days": subscription.plan.duration_days,
                },
            }

        wallet_data = None
        if wallet:
            wallet_data = {
                "balance": str(wallet.balance),
                "unit_name": wallet.unit.name,
                "one_usd_is": wallet.unit.one_usd_is,
                "balance_usd": str(
                    round(float(wallet.balance) / wallet.unit.one_usd_is, 4)
                ),
            }

        return JsonResponse({
            "subscription": subscription_data,
            "wallet": wallet_data,
        })
