import type { TFunction } from "i18next";

const GROUP_I18N_KEYS: Record<string, string> = {
  basic: "integrations-mcp-tools-basic",
  media: "integrations-mcp-tools-media",
  documents: "integrations-mcp-tools-documents",
  email: "integrations-mcp-tools-email",
  conversation: "integrations-mcp-tools-conversation",
  tagging: "integrations-mcp-tools-tagging",
  training: "integrations-mcp-tools-training",
  plugins: "integrations-mcp-tools-plugins",
  other: "integrations-mcp-tools-other",
};

export function mcpToolGroupLabel(group: string, t: TFunction): string {
  const key = GROUP_I18N_KEYS[group];
  return key ? t(key) : group;
}
