import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { DashboardLayout } from "./DashboardLayout";
import NotificationsInboxPage from "./NotificationsInboxPage";
import NotificationSettingsPage from "./NotificationSettingsPage";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { useIsOrganizationOwner } from "../../hooks/useIsOrganizationOwner";
import { Group, SegmentedControl, Stack } from "@mantine/core";

/**
 * Notification inbox + notification rules. ?view=inbox (default) | ?view=rules
 */
export default function NotificationsHubPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const view = searchParams.get("view") === "rules" ? "rules" : "inbox";
  const canSetNotifications = useIsFeatureEnabled("can-set-notifications");
  const isOrgOwner = useIsOrganizationOwner();

  const flagsResolved =
    canSetNotifications !== null && isOrgOwner !== null;
  const canManageNotificationRules =
    canSetNotifications === true || isOrgOwner === true;

  useEffect(() => {
    if (!flagsResolved || view !== "rules") return;
    if (!canManageNotificationRules) {
      const next = new URLSearchParams(searchParams);
      next.delete("view");
      setSearchParams(next, { replace: true });
    }
  }, [
    flagsResolved,
    canManageNotificationRules,
    view,
    searchParams,
    setSearchParams,
  ]);

  const setView = (v: string) => {
    const next = new URLSearchParams(searchParams);
    if (v === "inbox") {
      next.delete("view");
    } else {
      next.set("view", "rules");
    }
    setSearchParams(next);
  };

  const showRulesToggle =
    flagsResolved && canManageNotificationRules;

  return (
    <DashboardLayout>
      <Stack gap="lg">
        {showRulesToggle && (
          <Group justify="center">
            <SegmentedControl
              value={view}
              onChange={setView}
              data={[
                {
                  value: "inbox",
                  label: t("view-notifications-inbox") || "Inbox",
                },
                {
                  value: "rules",
                  label: t("view-notification-rules") || "Rules",
                },
              ]}
            />
          </Group>
        )}
        {view === "inbox" ? (
          <NotificationsInboxPage />
        ) : (
          <NotificationSettingsPage />
        )}
      </Stack>
    </DashboardLayout>
  );
}
