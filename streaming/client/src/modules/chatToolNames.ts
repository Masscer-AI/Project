/**
 * Always-on tools for the main chat, regardless of per-agent selection.
 * Mirrors the previous hardcoded baseline in chat/page.tsx.
 */
export const CHAT_REQUIRED_TOOL_NAMES = [
  "read_attachment",
  "list_attachments",
  "generate_document_file",
  "send_email",
  "list_organization_members",
  "list_organization_roles",
] as const;

/** Effective tool_names for one agent: required baseline + its own selection, deduped. */
export function effectiveChatToolNames(selected: string[] | undefined): string[] {
  return Array.from(new Set([...CHAT_REQUIRED_TOOL_NAMES, ...(selected ?? [])]));
}

/**
 * Builds the per-agent tool_names_by_agent map for a set of selected agent
 * slugs, using each agent's chosen tools from chatState.toolsByAgent.
 */
export function buildToolNamesByAgent(
  agentSlugs: string[],
  toolsByAgent: Record<string, string[]>
): Record<string, string[]> {
  const byAgent: Record<string, string[]> = {};
  for (const slug of agentSlugs) {
    byAgent[slug] = effectiveChatToolNames(toolsByAgent[slug]);
  }
  return byAgent;
}
