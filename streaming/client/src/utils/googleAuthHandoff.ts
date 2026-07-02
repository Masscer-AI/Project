import axios from "axios";
import { API_URL } from "../modules/constants";

export const GOOGLE_HANDOFF_SESSION_KEY = "masscer_google_handoff";

export type GoogleHandoffSession = {
  returnTo: string;
  next: string | null;
};

export function saveGoogleHandoffSession(session: GoogleHandoffSession): void {
  sessionStorage.setItem(GOOGLE_HANDOFF_SESSION_KEY, JSON.stringify(session));
}

export function loadGoogleHandoffSession(): GoogleHandoffSession | null {
  const raw = sessionStorage.getItem(GOOGLE_HANDOFF_SESSION_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as GoogleHandoffSession;
    if (!parsed?.returnTo) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function clearGoogleHandoffSession(): void {
  sessionStorage.removeItem(GOOGLE_HANDOFF_SESSION_KEY);
}

function googleCodeExchangeLockKey(code: string): string {
  return `masscer_google_exchange:${code}`;
}

/** Prevent duplicate code exchange (React StrictMode runs effects twice in dev). */
export function tryAcquireGoogleCodeExchangeLock(code: string): boolean {
  const key = googleCodeExchangeLockKey(code);
  const state = sessionStorage.getItem(key);
  if (state === "pending" || state === "done") {
    return false;
  }
  sessionStorage.setItem(key, "pending");
  return true;
}

export function markGoogleCodeExchangeDone(code: string): void {
  sessionStorage.setItem(googleCodeExchangeLockKey(code), "done");
}

export function releaseGoogleCodeExchangeLock(code: string): void {
  sessionStorage.removeItem(googleCodeExchangeLockKey(code));
}

export function isGoogleCodeExchangeDone(code: string): boolean {
  return sessionStorage.getItem(googleCodeExchangeLockKey(code)) === "done";
}

export function getGoogleAuthRedirectUri(): string {
  return `${window.location.origin}/auth/google`;
}

export async function postGoogleAuthAndHandoff(options: {
  access_token?: string;
  code?: string;
  redirect_uri?: string;
  return_to: string;
}): Promise<{ handoff_code: string; return_to: string }> {
  const response = await axios.post(`${API_URL}/v1/auth/google`, {
    ...(options.access_token ? { access_token: options.access_token } : {}),
    ...(options.code ? { code: options.code } : {}),
    ...(options.redirect_uri ? { redirect_uri: options.redirect_uri } : {}),
    return_to: options.return_to,
  });
  return response.data;
}

export function redirectToTenantHandoff(
  handoffCode: string,
  returnTo: string,
  next: string | null | undefined
): void {
  const callbackUrl = new URL("/auth/callback", returnTo);
  callbackUrl.searchParams.set("code", handoffCode);
  if (next) {
    callbackUrl.searchParams.set("next", next);
  }
  window.location.href = callbackUrl.toString();
}
