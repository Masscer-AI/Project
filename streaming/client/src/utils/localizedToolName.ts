import { useCallback } from "react";
import { useTranslation } from "react-i18next";

/** i18n key prefix shared with widget/WhatsApp capability labels. */
export function toolCapabilityTitleKey(toolSlug: string): string {
  return `widget-capability-${toolSlug}-title`;
}

export function localizedToolName(
  t: (key: string) => string,
  toolSlug: string | null | undefined
): string {
  if (!toolSlug) return "...";
  const key = toolCapabilityTitleKey(toolSlug);
  const label = t(key);
  if (label !== key) return label;
  return toolSlug.replace(/_/g, " ");
}

export function externalMcpToolTitleKey(
  catalogKey: string,
  remoteToolName: string
): string {
  const catalog = catalogKey.replace(/-/g, "_");
  return `external-mcp-${catalog}-${remoteToolName}-title`;
}

export function localizedExternalMcpToolName(
  t: (key: string) => string,
  catalogKey: string,
  remoteToolName: string
): string {
  const key = externalMcpToolTitleKey(catalogKey, remoteToolName);
  const label = t(key);
  if (label !== key) return label;
  return localizedToolName(t, remoteToolName);
}

export function useLocalizedToolName() {
  const { t } = useTranslation();
  return useCallback(
    (toolSlug: string | null | undefined) => localizedToolName(t, toolSlug),
    [t]
  );
}

export function useLocalizedExternalMcpToolName() {
  const { t } = useTranslation();
  return useCallback(
    (catalogKey: string, remoteToolName: string) =>
      localizedExternalMcpToolName(t, catalogKey, remoteToolName),
    [t]
  );
}
