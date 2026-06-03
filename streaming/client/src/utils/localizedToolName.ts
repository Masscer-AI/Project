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

export function useLocalizedToolName() {
  const { t } = useTranslation();
  return useCallback(
    (toolSlug: string | null | undefined) => localizedToolName(t, toolSlug),
    [t]
  );
}
