/** Build tenant subdomain URLs for dev (*.localhost) and prod (*.masscer.ai). */

export function getTenantBaseDomain(): string {
  if (typeof window === "undefined") return "masscer.ai";
  const hostname = window.location.hostname;
  if (hostname === "localhost" || hostname.endsWith(".localhost")) {
    return "localhost";
  }
  return "masscer.ai";
}

export function buildTenantSubdomainUrl(subdomain: string): string {
  const base = getTenantBaseDomain();
  const port =
    typeof window !== "undefined" && window.location.port
      ? `:${window.location.port}`
      : "";
  const protocol =
    typeof window !== "undefined" ? window.location.protocol : "https:";
  return `${protocol}//${subdomain}.${base}${port}`;
}

export function formatTenantSubdomainHost(subdomain: string): string {
  return `${subdomain}.${getTenantBaseDomain()}`;
}

const SUBDOMAIN_INPUT_RE = /^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

export function isValidSubdomainInput(value: string): boolean {
  const normalized = value.trim().toLowerCase();
  if (!normalized) return false;
  return SUBDOMAIN_INPUT_RE.test(normalized);
}
