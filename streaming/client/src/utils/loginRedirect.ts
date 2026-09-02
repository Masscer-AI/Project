import { getTeamFeatureFlags, getUserOrganizations } from "../modules/apiCalls";
import { TOrganization } from "../types";

const DEFAULT_POST_LOGIN_PATH = "/chat";
export const NO_CHAT_HOME_PATH = "/pld/expediente";
export const NO_ROLE_HOME_PATH = "/no-role";
export const AUTH_HOME_PATH = "/home";

export function isSafeInternalPath(path: string): boolean {
  if (!path.startsWith("/")) return false;
  if (path.startsWith("//")) return false;
  if (path.includes("://")) return false;
  if (path.toLowerCase().startsWith("/\\")) return false;
  if (/[\0-\x1f\x7f]/.test(path)) return false;
  return true;
}

export function encodeLoginNext(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (!isSafeInternalPath(normalized)) {
    throw new Error("Refusing to encode unsafe login redirect path");
  }
  return btoa(normalized);
}

export function decodeLoginNext(nextParam: string | null | undefined): string | null {
  if (!nextParam?.trim()) return null;
  try {
    const decoded = atob(nextParam.trim());
    return isSafeInternalPath(decoded) ? decoded : null;
  } catch {
    return null;
  }
}

export function loginUrlWithNext(path: string): string {
  try {
    const encoded = encodeLoginNext(path);
    return `/login?next=${encodeURIComponent(encoded)}`;
  } catch {
    return "/login";
  }
}

export function resolvePostLoginPath(
  nextParam: string | null | undefined,
  fallback: string = DEFAULT_POST_LOGIN_PATH
): string {
  return decodeLoginNext(nextParam) ?? fallback;
}

function isChatOnlyPath(path: string): boolean {
  return (
    path === "/chat" ||
    path.startsWith("/chat?") ||
    path.startsWith("/chat/") ||
    path === "/scheduled-tasks" ||
    path.startsWith("/scheduled-tasks?") ||
    path === "/gallery" ||
    path.startsWith("/gallery?")
  );
}

function isComplianceOnlyPath(path: string): boolean {
  return path === "/compliance" || path.startsWith("/compliance/") || path.startsWith("/compliance?");
}

function isExpedientePath(path: string): boolean {
  return path === "/pld/expediente" || path.startsWith("/pld/expediente?");
}

export async function userHasTeamFeature(flag: string): Promise<boolean> {
  try {
    const res = await getTeamFeatureFlags();
    return res.feature_flags?.[flag] === true;
  } catch {
    return false;
  }
}

export async function userCanUseChat(): Promise<boolean> {
  return userHasTeamFeature("can-use-chat");
}

function homeFromAccess(opts: {
  canUseChat: boolean;
  canAccessCompliance: boolean;
  orgs: TOrganization[];
}): string {
  const { canUseChat, canAccessCompliance, orgs } = opts;
  if (canUseChat) return DEFAULT_POST_LOGIN_PATH;
  if (canAccessCompliance) return "/compliance";
  if (orgs.length === 0) return NO_CHAT_HOME_PATH;
  return NO_ROLE_HOME_PATH;
}

export async function resolveAuthenticatedHome(
  nextParam: string | null | undefined
): Promise<string> {
  const [canUseChat, canAccessCompliance, orgs] = await Promise.all([
    userHasTeamFeature("can-use-chat"),
    userHasTeamFeature("organization-compliance-access"),
    getUserOrganizations().catch(() => [] as TOrganization[]),
  ]);
  const home = homeFromAccess({ canUseChat, canAccessCompliance, orgs });
  const next = decodeLoginNext(nextParam);
  if (!next) return home;
  if (!canUseChat && isChatOnlyPath(next)) return home;
  if (!canAccessCompliance && isComplianceOnlyPath(next)) return home;
  if (isExpedientePath(next) && orgs.length > 0) return home;
  return next;
}
