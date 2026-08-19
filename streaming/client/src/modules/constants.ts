const DEFAULT_API_URL = (() => {
  if (typeof window === "undefined") return "http://localhost:8000";
  const origin = window.location.origin;
  if (!origin || origin === "null" || origin.startsWith("file:")) return "http://localhost:8000";
  if (origin === "http://localhost:5173") return "http://localhost:8000";
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

export const MASSCER_WHATSAPP_URL = "https://wa.me/525580338745";