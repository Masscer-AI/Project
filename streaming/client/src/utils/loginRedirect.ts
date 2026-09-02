import { getTeamFeatureFlags } from "../modules/apiCalls";

const DEFAULT_POST_LOGIN_PATH = "/chat";
export const NO_CHAT_HOME_PATH = "/pld/expediente";

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

export async function userCanUseChat(): Promise<boolean> {
  try {
    const res = await getTeamFeatureFlags();
    return res.feature_flags?.["can-use-chat"] === true;
  } catch {
    return false;
  }
}

export async function resolveAuthenticatedHome(
  nextParam: string | null | undefined
): Promise<string> {
  const canUseChat = await userCanUseChat();
  const home = canUseChat ? DEFAULT_POST_LOGIN_PATH : NO_CHAT_HOME_PATH;
  const next = decodeLoginNext(nextParam);
  if (!next) return home;
  if (!canUseChat && isChatOnlyPath(next)) return home;
  return next;
}
