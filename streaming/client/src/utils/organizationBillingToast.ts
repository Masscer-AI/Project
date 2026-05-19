import toast from "react-hot-toast";
import i18n from "../i18next";

const REASON_TO_KEY: Record<string, string> = {
  subscription_expired: "organization-billing-blocked-subscription-expired",
  subscription_expired_with_purchased_locked:
    "organization-billing-blocked-subscription-expired-with-purchased-locked",
  out_of_balance: "organization-billing-blocked-out-of-balance",
  no_subscription: "organization-billing-blocked-no-subscription",
  no_org_wallet: "organization-billing-blocked-no-org-wallet",
  billing_check_error: "organization-billing-blocked-billing-check-error",
};

/** Toast when org billing blocks the agent task (matches backend billing_reason). */
export function showOrganizationBillingBlockedToast(billingReason?: string) {
  const key =
    (billingReason && REASON_TO_KEY[billingReason]) ||
    "organization-billing-blocked-generic";
  toast.error(i18n.t(key));
}
