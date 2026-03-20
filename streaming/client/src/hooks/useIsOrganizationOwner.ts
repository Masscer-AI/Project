import { useEffect, useState } from "react";
import { getUserOrganizations } from "../modules/apiCalls";
import { useStore } from "../modules/store";

function orgIndicatesCurrentUserOwns(
  orgs: Awaited<ReturnType<typeof getUserOrganizations>>,
  userId: number
): boolean {
  const uid = String(userId);
  return orgs.some(
    (o) =>
      o.is_owner === true ||
      (o.owner != null && String(o.owner) === uid)
  );
}

/** True if the user owns at least one organization returned by /v1/auth/organizations/. */
export function useIsOrganizationOwner(): boolean | null {
  const user = useStore((s) => s.user);
  const [isOwner, setIsOwner] = useState<boolean | null>(null);

  useEffect(() => {
    const uid = user?.id;
    if (uid == null) {
      setIsOwner(null);
      return;
    }
    let cancelled = false;
    void getUserOrganizations()
      .then((orgs) => {
        if (!cancelled) {
          setIsOwner(orgIndicatesCurrentUserOwns(orgs, uid));
        }
      })
      .catch(() => {
        if (!cancelled) {
          setIsOwner(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [user?.id]);

  return isOwner;
}
