import { useEffect, useState } from "react";
import { getCompletion } from "../modules/apiCalls";

/**
 * Fetches current `approved` from the API for the given completion ids.
 * Message attachments store a snapshot at send time; this keeps badges in sync after KB approval.
 */
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
            /* keep previous / fall back to attachment snapshot */
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
