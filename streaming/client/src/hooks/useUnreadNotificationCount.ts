import { useEffect, useState } from "react";
import { useStore } from "../modules/store";
import { getMyNotifications } from "../modules/apiCalls";
import { NOTIFICATIONS_INBOX_UPDATED_EVENT } from "../utils/notificationInboxEvents";

export function formatUnreadNotificationBadge(count: number): string {
  return count > 99 ? "99+" : String(count);
}

/**
 * Unread in-app notifications (same source as Sidebar dashboard badge).
 * Listens for inbox push (`masscer:notifications-updated`) and visibility / poll.
 */
export function useUnreadNotificationCount(): number {
  const user = useStore((s) => s.user);
  const [count, setCount] = useState(0);

  useEffect(() => {
    if (!user) {
      setCount(0);
      return;
    }
    let cancelled = false;
    const refreshUnread = () => {
      getMyNotifications({ unread: true })
        .then((rows) => {
          if (!cancelled) setCount(rows.length);
        })
        .catch(() => {
          if (!cancelled) setCount(0);
        });
    };
    refreshUnread();
    const intervalId = window.setInterval(refreshUnread, 45_000);
    const onVisibility = () => {
      if (document.visibilityState === "visible") refreshUnread();
    };
    const onInboxUpdated = () => refreshUnread();
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener(NOTIFICATIONS_INBOX_UPDATED_EVENT, onInboxUpdated);
    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener(NOTIFICATIONS_INBOX_UPDATED_EVENT, onInboxUpdated);
    };
  }, [user]);

  return count;
}
