// Widget: uses WIDGET_API_URL set by loader (needed for file:// or cross-origin embeds).
// Main app: uses VITE_API_URL. Use ?? so empty string "" is preserved (same-origin), only null/undefined get default.
const DEFAULT_API_URL = (() => {
  if (typeof window === "undefined") return "http://localhost:8000";
  const origin = window.location.origin;
  if (!origin || origin === "null" || origin.startsWith("file:")) return "http://localhost:8000";
  if (origin === "http://localhost:5173") return "http://localhost:8000";
  // In deployed environments, prefer same-origin requests by default.
  return "";
})();

export const API_URL =
  (typeof window !== "undefined" && (window as any).WIDGET_API_URL) ||
  // @ts-ignore
  (import.meta.env.VITE_API_URL ?? DEFAULT_API_URL);
export const STREAMING_BACKEND_URL = (() => {
  const origin = window.location.origin;
  if (origin === "http://localhost:5173") return "http://localhost:8001";
  if (!origin || origin === "null" || origin.startsWith("file:"))
    return "http://localhost:8001";
  return origin;
})();

export const PUBLIC_TOKEN =
  // @ts-ignore
  import.meta.env.VITE_PUBLIC_TOKEN || "39ece367b84b4bd19622692cc70361f2";

export const DEFAULT_ORGANIZATION_ID =
  // @ts-ignore
  import.meta.env.VITE_DEFAULT_ORGANIZATION_ID || null;