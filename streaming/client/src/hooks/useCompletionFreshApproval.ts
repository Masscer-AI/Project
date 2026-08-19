import { useEffect, useState } from "react";
import { getCompletion } from "../modules/apiCalls";

export function useCompletionFreshApproval(completionIds: string[]): Record<string, boolean> {
  const [approvedById, setApprovedById] = useState<Record<string, boolean>>({});

  const sortedUnique = [...new Set(completionIds.filter((id) => /^\d+$/.test(id)))].sort();
  const depsKey = sortedUnique.join(",");

  useEffect(() => {
    if (sortedUnique.length === 0) {
      setApprovedById({});
      return;
    }

    let cancelled = false;

    void (async () => {
      const updates: Record<string, boolean> = {};
      await Promise.all(
        sortedUnique.map(async (id) => {
          try {
            const c = await getCompletion(id);
            updates[id] = Boolean(c.approved);
          } catch {
          }
        })
      );
      if (!cancelled) {
        setApprovedById((prev) => ({ ...prev, ...updates }));
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [depsKey]);

  return approvedById;
}
