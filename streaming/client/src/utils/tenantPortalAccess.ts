import { getCanonicalAppOrigin } from "./tenantSubdomain";

export const WRONG_ORGANIZATION_PORTAL_CODE = "wrong_organization_portal";
export const TENANT_PORTAL_SIGNUP_FORBIDDEN_CODE = "tenant_portal_signup_forbidden";

type PortalAccessErrorData = {
  code?: string;
  redirect_to?: string;
  error?: string;
};

export function getPortalOriginPayload():
  | { portal_origin: string }
  | Record<string, never> {
  if (typeof window === "undefined") return {};
  return { portal_origin: window.location.origin };
}

export function getPortalAccessErrorData(
  error: unknown
): PortalAccessErrorData | null {
  const axiosErr = error as {
    response?: { data?: PortalAccessErrorData };
  };
  return axiosErr.response?.data ?? null;
}

/** Redirect to the main app when the user cannot access this tenant portal. */
export function handleTenantPortalAccessError(error: unknown): boolean {
  const data = getPortalAccessErrorData(error);
  if (!data?.code) return false;

  if (
    data.code !== WRONG_ORGANIZATION_PORTAL_CODE &&
    data.code !== TENANT_PORTAL_SIGNUP_FORBIDDEN_CODE
  ) {
    return false;
  }

  const redirect =
    data.redirect_to?.trim() || `${getCanonicalAppOrigin()}/login`;
  window.location.href = redirect;
  return true;
}
