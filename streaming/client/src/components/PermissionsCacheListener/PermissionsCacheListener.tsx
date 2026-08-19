import { useEffect } from "react";
import { useStore } from "../../modules/store";

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
