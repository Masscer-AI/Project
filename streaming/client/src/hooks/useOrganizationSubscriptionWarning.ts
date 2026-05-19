import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import {
  getOrganizationBilling,
  getUserOrganizations,
} from "../modules/apiCalls";
import { useStore } from "../modules/store";
import type { TOrganization, TOrganizationBilling } from "../types";

export type OrganizationSubscriptionWarningKind =
  | "none"
  | "no_subscription"
  | "inactive"
  | "inactive_with_purchased";

type WarningState = {
  canManage: boolean;
  kind: OrganizationSubscriptionWarningKind;
  loading: boolean;
};

const INITIAL: WarningState = {
  canManage: false,
  kind: "none",
  loading: true,
};

function isManageableOrg(org: TOrganization, userId: number | undefined): boolean {
  if (org.is_owner || org.can_manage) return true;
  if (userId != null && org.owner === userId) return true;
  return false;
}

/** Same signals as the organization billing tab (status badge + is_active). */
export function subscriptionWarningKind(
  billing: TOrganizationBilling
): OrganizationSubscriptionWarningKind {
  const sub = billing.subscription;
  if (!sub) return "no_subscription";

  const inactiveStatus = ["expired", "cancelled", "pending_payment"].includes(
    sub.status
  );
  if (!sub.is_active || inactiveStatus) {
    const purchased = parseFloat(billing.wallet?.purchased_balance_usd ?? "0");
    return purchased > 0 ? "inactive_with_purchased" : "inactive";
  }
  return "none";
}

/**
 * For users who can manage an organization (owner / can_manage): whether to show
 * a subscription warning banner (no subscription or inactive subscription).
 */
export function useOrganizationSubscriptionWarning() {
  const userId = useStore((s) => s.user?.id);
  const location = useLocation();
  const [state, setState] = useState<WarningState>(INITIAL);

  useEffect(() => {
    let cancelled = false;
    const token = localStorage.getItem("token");
    if (!token) {
      setState({ canManage: false, kind: "none", loading: false });
      return;
    }

    setState((prev) => ({ ...prev, loading: true }));

    (async () => {
      try {
        const orgs = await getUserOrganizations();
        const manageable = orgs.filter((o) => isManageableOrg(o, userId));
        if (!manageable.length) {
          if (!cancelled) {
            setState({ canManage: false, kind: "none", loading: false });
          }
          return;
        }

        // Prefer owned orgs, then first org that needs a warning.
        const ordered = [
          ...manageable.filter((o) => o.is_owner || o.owner === userId),
          ...manageable.filter((o) => !o.is_owner && o.owner !== userId),
        ];

        let warningKind: OrganizationSubscriptionWarningKind = "none";
        for (const org of ordered) {
          try {
            const billing = await getOrganizationBilling(org.id);
            if (cancelled) return;
            const kind = subscriptionWarningKind(billing);
            if (kind !== "none") {
              warningKind = kind;
              break;
            }
          } catch {
            // Try next org (e.g. forbidden on one membership).
          }
        }

        if (!cancelled) {
          setState({
            canManage: true,
            kind: warningKind,
            loading: false,
          });
        }
      } catch {
        if (!cancelled) {
          setState({ canManage: false, kind: "none", loading: false });
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [userId, location.pathname]);

  const showBanner =
    state.canManage && state.kind !== "none" && !state.loading;

  return {
    showBanner,
    kind: state.kind,
    billingHref: "/organization?activeTab=billing",
  };
}
