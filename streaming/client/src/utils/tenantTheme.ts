import { createTheme, type MantineTheme } from "@mantine/core";
import { API_URL } from "../modules/constants";
import type { TTenantBranding } from "../modules/storeTypes";

type MantineShades = [
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
  string,
];

const DEFAULT_THEME = createTheme({
  primaryColor: "violet",
});

type Rgb = { r: number; g: number; b: number };

function expandHex(hex: string): string {
  if (hex.length === 4) {
    return `#${hex[1]}${hex[1]}${hex[2]}${hex[2]}${hex[3]}${hex[3]}`;
  }
  return hex;
}

function hexToRgb(hex: string): Rgb | null {
  const normalized = expandHex(hex.trim());
  const match = /^#([0-9a-fA-F]{6})$/.exec(normalized);
  if (!match) return null;
  const value = match[1];
  return {
    r: parseInt(value.slice(0, 2), 16),
    g: parseInt(value.slice(2, 4), 16),
    b: parseInt(value.slice(4, 6), 16),
  };
}

function mixRgb(a: Rgb, b: Rgb, weight: number): Rgb {
  return {
    r: Math.round(a.r * (1 - weight) + b.r * weight),
    g: Math.round(a.g * (1 - weight) + b.g * weight),
    b: Math.round(a.b * (1 - weight) + b.b * weight),
  };
}

function rgbToHex({ r, g, b }: Rgb): string {
  const toPart = (n: number) => n.toString(16).padStart(2, "0");
  return `#${toPart(r)}${toPart(g)}${toPart(b)}`;
}

function shadesFromHex(hex: string): string[] {
  const base = hexToRgb(hex);
  if (!base) return [];
  const white = { r: 255, g: 255, b: 255 };
  const black = { r: 0, g: 0, b: 0 };
  return [
    rgbToHex(mixRgb(base, white, 0.9)),
    rgbToHex(mixRgb(base, white, 0.75)),
    rgbToHex(mixRgb(base, white, 0.55)),
    rgbToHex(mixRgb(base, white, 0.35)),
    rgbToHex(mixRgb(base, white, 0.15)),
    rgbToHex(base),
    rgbToHex(mixRgb(base, black, 0.1)),
    rgbToHex(mixRgb(base, black, 0.25)),
    rgbToHex(mixRgb(base, black, 0.4)),
    rgbToHex(mixRgb(base, black, 0.55)),
  ];
}

export const PRIMARY_COLOR_VAR = "var(--mantine-primary-color-5)";
export const PRIMARY_COLOR_3 = "var(--mantine-primary-color-3)";
export const PRIMARY_COLOR_7 = "var(--mantine-primary-color-7)";
export const PRIMARY_COLOR_9 = "var(--mantine-primary-color-9)";

/** Translucent tint from tenant primary color (alpha 0–1). */
export const primaryAlpha = (alpha: number) =>
  `color-mix(in srgb, ${PRIMARY_COLOR_VAR} ${Math.round(alpha * 100)}%, transparent)`;

export const primaryShadeAlpha = (shadeVar: string, alpha: number) =>
  `color-mix(in srgb, ${shadeVar} ${Math.round(alpha * 100)}%, transparent)`;

export const LANDING_HERO_BACKGROUND = `radial-gradient(ellipse 100% 80% at 50% -10%, ${primaryShadeAlpha(PRIMARY_COLOR_7, 0.4)} 0%, transparent 55%), radial-gradient(circle at 80% 90%, ${primaryAlpha(0.12)} 0%, transparent 50%), radial-gradient(circle at 20% 30%, ${primaryShadeAlpha(PRIMARY_COLOR_9, 0.15)} 0%, transparent 50%), #050508`;

export const AUTH_PANEL_LEFT_BACKGROUND = `radial-gradient(ellipse 80% 60% at 30% 50%, ${primaryAlpha(0.15)}, transparent), linear-gradient(180deg, rgba(20,20,25,0.98) 0%, rgba(15,15,20,0.99) 100%)`;

export const BRANDING_ICON_BOX_STYLE = {
  background: primaryAlpha(0.2),
  border: `1px solid ${primaryAlpha(0.3)}`,
} as const;

export const AUTH_FORM_CARD_CLASS =
  "w-full max-w-[400px] p-10 rounded-2xl shadow-2xl";

export const AUTH_FORM_CARD_STYLE = {
  background: `linear-gradient(180deg, color-mix(in srgb, rgba(18, 18, 22, 0.98) 90%, ${PRIMARY_COLOR_VAR} 10%) 0%, rgba(10, 10, 12, 0.99) 100%)`,
  border: `1px solid ${primaryAlpha(0.18)}`,
  boxShadow: `0 25px 50px -12px rgba(0, 0, 0, 0.55), 0 0 32px ${primaryAlpha(0.06)}`,
} as const;

export const AUTH_INPUT_STYLES = {
  input: {
    backgroundColor: `color-mix(in srgb, var(--mantine-color-dark-6) 88%, ${PRIMARY_COLOR_VAR} 12%)`,
    borderColor: primaryAlpha(0.12),
  },
} as const;

export function buildMantineTheme(
  branding: TTenantBranding | null | undefined
): MantineTheme {
  const primaryColor = branding?.theme?.primary_color?.trim();
  if (!primaryColor) return DEFAULT_THEME;

  const shades = shadesFromHex(primaryColor);
  if (shades.length !== 10) return DEFAULT_THEME;

  // Override the violet palette so existing color="violet" and
  // var(--mantine-color-violet-*) usages follow tenant branding.
  return createTheme({
    primaryColor: "violet",
    colors: {
      violet: shades as MantineShades,
    },
  });
}

function applyTenantLegacyColorVariables(
  primaryColor: string | null | undefined
): void {
  const root = document.documentElement;
  const hex = primaryColor?.trim();
  if (!hex) {
    root.style.removeProperty("--active-color");
    root.style.removeProperty("--highlighted-color");
    root.style.removeProperty("--highlighted-color-opaque");
    return;
  }

  const rgb = hexToRgb(hex);
  if (!rgb) return;

  const { r, g, b } = rgb;
  root.style.setProperty("--active-color", `rgb(${r}, ${g}, ${b})`);
  root.style.setProperty(
    "--highlighted-color",
    `rgba(${r}, ${g}, ${b}, 0.8)`
  );
  root.style.setProperty(
    "--highlighted-color-opaque",
    `rgba(${r}, ${g}, ${b}, 0.35)`
  );
}

export function applyTenantBranding(
  branding: TTenantBranding | null | undefined
): void {
  applyTenantDocumentBranding(branding);
  applyTenantLegacyColorVariables(branding?.theme?.primary_color);
}

export function resolveTenantBranding(
  config: TTenantBranding | null | undefined
): TTenantBranding | null {
  if (!config) return null;
  const hasBranding = Boolean(
    config.app_name ||
      config.logo_url ||
      config.favicon_url ||
      config.theme?.primary_color ||
      config.hide_powered_by
  );
  return hasBranding ? config : null;
}

export const DEFAULT_DOCUMENT_TITLE = "Masscer AI - Everything in the same place";

export function applyTenantDocumentBranding(
  branding: TTenantBranding | null | undefined
): void {
  document.title = branding?.app_name || DEFAULT_DOCUMENT_TITLE;

  const faviconHref = branding?.favicon_url || branding?.logo_url;
  const existing = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (!faviconHref) {
    if (existing) existing.href = "./assets/favicon.ico";
    return;
  }

  const href =
    faviconHref.startsWith("http://") ||
    faviconHref.startsWith("https://") ||
    faviconHref.startsWith("data:")
      ? faviconHref
      : `${API_URL}${faviconHref}`;

  if (existing) {
    existing.href = href;
    return;
  }

  const link = document.createElement("link");
  link.rel = "icon";
  link.href = href;
  document.head.appendChild(link);
}
