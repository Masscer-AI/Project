import React from "react";
import { Navigate, useSearchParams } from "react-router-dom";

/**
 * @deprecated Use /dashboard/alerts?view=notifications (or notify-rules).
 * Preserves bookmarks: /dashboard/notifications → inbox, ?view=rules → notification rules editor.
 */
export default function NotificationsHubPage() {
  const [params] = useSearchParams();
  const view = params.get("view");
  const to =
    view === "rules"
      ? "/dashboard/alerts?view=notify-rules"
      : "/dashboard/alerts?view=notifications";
  return <Navigate to={to} replace />;
}
