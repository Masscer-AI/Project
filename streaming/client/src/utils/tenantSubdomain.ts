/** Build tenant subdomain URLs from the current browser host (localhost, prod, tunnels). */

const PROD_TENANT_SUFFIX = ".masscer.ai";

const RESERVED_HOST_LABELS = new Set([
  "app",
  "core",
  "www",
  "api",
  "admin",
  "static",
  "media",
  "mail",
  "ftp",
  "localhost",
]);

function currentHostname(): string {
  if (typeof window === "undefined") return "";
  return window.location.hostname.toLowerCase();
}

/**
 * If hostname is a tenant portal host, return its single subdomain label; else null.
 * Examples: acme.localhost → acme; charly.masscer-ai.ngrok.app → charly.
 */
function getTenantLabel(hostname: string): string | null {
  if (!hostname || hostname === "localhost" || hostname === "127.0.0.1") {
    return null;
  }

  if (hostname.endsWith(".localhost")) {
    const label = hostname.slice(0, -".localhost".length);
    if (label.length > 0 && !label.includes(".") && !RESERVED_HOST_LABELS.has(label)) {
      return label;
    }
    return null;
  }

  if (hostname.startsWith("app.")) {
    return null;
  }

  if (hostname.endsWith(PROD_TENANT_SUFFIX)) {
    const label = hostname.slice(0, -PROD_TENANT_SUFFIX.length);
    if (label.length > 0 && !label.includes(".") && !RESERVED_HOST_LABELS.has(label)) {
      return label;
    }
    return null;
  }

  // Tunnels / custom hosts: tenant = one extra label on the canonical host.
  // e.g. charly.masscer-ai.ngrok.app (4 parts) vs masscer-ai.ngrok.app (3 parts).
  const firstDot = hostname.indexOf(".");
  if (firstDot <= 0) return null;
  const label = hostname.slice(0, firstDot);
  const rest = hostname.slice(firstDot + 1);
  if (
    label &&
    !label.includes(".") &&
    !RESERVED_HOST_LABELS.has(label) &&
    rest.includes(".") &&
    hostname.split(".").length >= 4
  ) {
    return label;
  }

  return null;
}

/**
 * Domain suffix for tenant portals: acme.{return value}.
 * Derived from window.location.hostname (canonical or tenant host).
 */
export function getTenantBaseDomain(hostname: string = currentHostname()): string {
  if (!hostname || hostname === "localhost" || hostname === "127.0.0.1") {
    return "localhost";
  }

  if (hostname.endsWith(".localhost")) {
    return "localhost";
  }

  if (hostname.startsWith("app.")) {
    return hostname.slice("app.".length);
  }

  const tenantLabel = getTenantLabel(hostname);
  if (tenantLabel) {
    return hostname.slice(tenantLabel.length + 1);
  }

  // Canonical app host (e.g. masscer-ai.ngrok.app, masscer.ai) — tenants are {sub}.{this}.
  return hostname;
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

/** True when the current host is a tenant portal (e.g. acme.localhost), not the canonical app. */
export function isTenantSubdomainHost(): boolean {
  return getTenantLabel(currentHostname()) !== null;
}

/** Canonical app origin where Google Sign-In JavaScript origins are registered. */
export function getCanonicalAppOrigin(): string {
  const hostname = currentHostname();
  const port =
    typeof window !== "undefined" && window.location.port
      ? `:${window.location.port}`
      : "";
  const protocol =
    typeof window !== "undefined" ? window.location.protocol : "https:";
  const base = getTenantBaseDomain(hostname);

  if (base === "localhost") {
    return `${protocol}//localhost${port}`;
  }

  if (base === "masscer.ai") {
    return `${protocol}//app.masscer.ai`;
  }

  // Tunnel / custom canonical host (e.g. masscer-ai.ngrok.app).
  return `${protocol}//${base}${port}`;
}

export function buildTenantGoogleBridgeUrl(options: {
  returnTo: string;
  next?: string | null;
}): string {
  const url = new URL("/auth/google", getCanonicalAppOrigin());
  url.searchParams.set("return_to", options.returnTo);
  if (options.next) {
    url.searchParams.set("next", options.next);
  }
  return url.toString();
}

/** @deprecated Use buildTenantGoogleBridgeUrl for tenant Google Sign-In. */
export function buildCanonicalGoogleAuthUrl(options: {
  path: "/login" | "/signup";
  returnTo: string;
  next?: string | null;
}): string {
  return buildTenantGoogleBridgeUrl({
    returnTo: options.returnTo,
    next: options.next,
  });
}
