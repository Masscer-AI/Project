import type { TAgent } from "../types/agents";

/**
 * Chat agent selection is owned exclusively by `chatState.selectedAgents` (slug order).
 * `related_agents` on the conversation is hydrated into that list via `applyAgentSelectionFromConversation`.
 */
export function agentsInChatSelectionOrder(
  agents: TAgent[],
  selectedSlugs: string[]
): TAgent[] {
  const bySlug = new Map(agents.map((a) => [a.slug, a]));
  return selectedSlugs
    .map((slug) => bySlug.get(slug))
    .filter((a): a is TAgent => a != null);
}

/** Selected agents first (in slug-list order), then the rest in list order. */
export function sortAgentsBySelectionOrder(
  agents: TAgent[],
  selectedSlugs: string[]
): TAgent[] {
  const selectedSet = new Set(selectedSlugs);
  const head = agentsInChatSelectionOrder(agents, selectedSlugs);
  const tail = agents.filter((a) => !selectedSet.has(a.slug));
  return [...head, ...tail];
}
