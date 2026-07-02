const DEFAULT_POST_LOGIN_PATH = "/chat";

/** Reject open redirects and non-app paths. */
export function isSafeInternalPath(path: string): boolean {
  if (!path.startsWith("/")) return false;
  if (path.startsWith("//")) return false;
  if (path.includes("://")) return false;
  if (path.toLowerCase().startsWith("/\\")) return false;
  if (/[\0-\x1f\x7f]/.test(path)) return false;
  return true;
}

/** Base64-encode an internal path for use in ?next= */
export function encodeLoginNext(path: string): string {
  const normalized = path.startsWith("/") ? path : `/${path}`;
  if (!isSafeInternalPath(normalized)) {
    throw new Error("Refusing to encode unsafe login redirect path");
  }
  return btoa(normalized);
}

/** Decode ?next= (base64) to an internal path, or null if missing/invalid. */
export function decodeLoginNext(nextParam: string | null | undefined): string | null {
  if (!nextParam?.trim()) return null;
  try {
    const decoded = atob(nextParam.trim());
    return isSafeInternalPath(decoded) ? decoded : null;
  } catch {
    return null;
  }
}

/** Build /login?next=… for redirecting unauthenticated users. */
export function loginUrlWithNext(path: string): string {
  try {
    const encoded = encodeLoginNext(path);
    return `/login?next=${encodeURIComponent(encoded)}`;
  } catch {
    return "/login";
  }
}

/** Post-login destination from ?next=, falling back to /chat. */
export function resolvePostLoginPath(
  nextParam: string | null | undefined,
  fallback: string = DEFAULT_POST_LOGIN_PATH
): string {
  return decodeLoginNext(nextParam) ?? fallback;
}
