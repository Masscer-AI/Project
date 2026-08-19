
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

  const parts = hostname.split(".");
  const label = parts[0];

  if (RESERVED_HOST_LABELS.has(label)) {
    return null;
  }
  if (parts.length < 3) {
    return null;
  }

  return label;
}

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

export function isTenantSubdomainHost(): boolean {
  return getTenantLabel(currentHostname()) !== null;
}

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

  return `${protocol}//app.${base}${port}`;
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
