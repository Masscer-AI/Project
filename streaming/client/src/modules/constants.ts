export const API_URL =
  // @ts-ignore
  import.meta.env.VITE_API_URL || "http://localhost:8000";
export const STREAMING_BACKEND_URL =
  window.location.origin === "http://localhost:5173"
    ? "http://localhost:8001"
    : window.location.origin;

export const PUBLIC_TOKEN =
  // @ts-ignore
  import.meta.env.VITE_PUBLIC_TOKEN || "39ece367b84b4bd19622692cc70361f2";
