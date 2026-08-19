const DEFAULT_POST_LOGIN_PATH = "/chat";

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
