import { useEffect } from "react";
import { useStore } from "../../modules/store";

/**
 * When the server invalidates feature-flag caches (roles, assignments, etc.),
 * it emits `invalidate-permissions-cache` on the user’s Socket.IO route so the
 * client refetches GET /v1/auth/feature-flags/ and bypasses the 30m client TTL.
 */
export function PermissionsCacheListener() {
  const user = useStore((s) => s.user);
  const socket = useStore((s) => s.socket);
  const ensureFeatureFlags = useStore((s) => s.ensureFeatureFlags);

  useEffect(() => {
    if (!user?.id) return;

    const handler = () => {
      void ensureFeatureFlags({ force: true });
    };

    socket.on("invalidate-permissions-cache", handler);
    return () => {
      socket.off("invalidate-permissions-cache", handler);
    };
  }, [user?.id, socket, ensureFeatureFlags]);

  return null;
}
