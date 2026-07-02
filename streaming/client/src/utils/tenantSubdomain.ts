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

/** True when the current host is a tenant portal (e.g. acme.localhost), not the canonical app. */
export function isTenantSubdomainHost(): boolean {
  if (typeof window === "undefined") return false;
  const hostname = window.location.hostname;
  if (!hostname || hostname === "localhost" || hostname === "127.0.0.1") {
    return false;
  }
  if (hostname.endsWith(".localhost")) {
    const label = hostname.slice(0, -".localhost".length);
    return label.length > 0 && !label.includes(".") && !RESERVED_HOST_LABELS.has(label);
  }
  const base = getTenantBaseDomain();
  if (hostname === base || hostname === `app.${base}` || hostname === `www.${base}`) {
    return false;
  }
  if (hostname.endsWith(`.${base}`)) {
    const label = hostname.slice(0, -(base.length + 1));
    return label.length > 0 && !label.includes(".") && !RESERVED_HOST_LABELS.has(label);
  }
  return false;
}

/** Canonical app origin where Google Sign-In JavaScript origins are registered. */
export function getCanonicalAppOrigin(): string {
  const base = getTenantBaseDomain();
  const port =
    typeof window !== "undefined" && window.location.port
      ? `:${window.location.port}`
      : "";
  const protocol =
    typeof window !== "undefined" ? window.location.protocol : "https:";
  if (base === "localhost") {
    return `${protocol}//localhost${port}`;
  }
  return `https://app.${base}`;
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
