import type { TAgent } from "../types/agents";

export function agentsInChatSelectionOrder(
  agents: TAgent[],
  selectedSlugs: string[]
): TAgent[] {
  const bySlug = new Map(agents.map((a) => [a.slug, a]));
  return selectedSlugs
    .map((slug) => bySlug.get(slug))
    .filter((a): a is TAgent => a != null);
}

export function sortAgentsBySelectionOrder(
  agents: TAgent[],
  selectedSlugs: string[]
): TAgent[] {
  const selectedSet = new Set(selectedSlugs);
  const head = agentsInChatSelectionOrder(agents, selectedSlugs);
  const tail = agents.filter((a) => !selectedSet.has(a.slug));
  return [...head, ...tail];
}
