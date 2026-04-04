import React, { useEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { DashboardLayout } from "./DashboardLayout";
import AlertsPage from "./AlertsPage";
import AlertRulesPage from "./AlertRulesPage";
import NotificationsInboxPage from "./NotificationsInboxPage";
import NotificationSettingsPage from "./NotificationSettingsPage";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { useIsOrganizationOwner } from "../../hooks/useIsOrganizationOwner";
import { Group, Loader, SegmentedControl, Stack } from "@mantine/core";

export type AlertsHubView =
  | "notifications"
  | "alerts"
  | "rules"
  | "notify-rules";

/** Maps URL ?view= to hub section. Legacy: list → alerts, inbox → notifications. */
export function parseAlertsHubView(
  searchParams: URLSearchParams
): AlertsHubView {
  const v = (searchParams.get("view") || "").toLowerCase();
  if (v === "rules") return "rules";
  if (v === "notify-rules" || v === "notification-rules") return "notify-rules";
  if (v === "notifications" || v === "inbox") return "notifications";
  if (v === "alerts" || v === "list") return "alerts";
  if (searchParams.get("conversation")) return "alerts";
  return "notifications";
}

/**
 * In-app notifications inbox, alert queue (resolve/dismiss), alert rules, notification rules.
 * ?view=notifications | alerts | rules | notify-rules (default: notifications)
 */
export default function AlertsHubPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();

  const canManageAlertRules = useIsFeatureEnabled("alert-rules-manager");
  const canSetNotifications = useIsFeatureEnabled("can-set-notifications");
  const isOrgOwner = useIsOrganizationOwner();

  const flagsResolved =
    canManageAlertRules !== null &&
    canSetNotifications !== null &&
    isOrgOwner !== null;

  const canManageNotificationRules =
    canSetNotifications === true || isOrgOwner === true;

  const parsedView = parseAlertsHubView(searchParams);

  const effectiveView = useMemo((): AlertsHubView => {
    if (parsedView === "rules" && flagsResolved && canManageAlertRules === false) {
      return "notifications";
    }
    if (
      parsedView === "notify-rules" &&
      flagsResolved &&
      !canManageNotificationRules
    ) {
      return "notifications";
    }
    return parsedView;
  }, [
    parsedView,
    flagsResolved,
    canManageAlertRules,
    canManageNotificationRules,
  ]);

  useEffect(() => {
    if (!flagsResolved) return;
    if (effectiveView === parsedView) return;
    const next = new URLSearchParams(searchParams);
    next.set("view", effectiveView);
    setSearchParams(next, { replace: true });
  }, [
    flagsResolved,
    effectiveView,
    parsedView,
    searchParams,
    setSearchParams,
  ]);

  const segmentData = useMemo(() => {
    const items: { value: AlertsHubView; label: string }[] = [
      {
        value: "notifications",
        label: t("view-notifications-inbox") || "Notifications",
      },
      {
        value: "alerts",
        label: t("view-alerts-queue") || "Alerts",
      },
    ];
    if (flagsResolved && canManageAlertRules) {
      items.push({
        value: "rules",
        label: t("view-alert-rules") || "Alert rules",
      });
    }
    if (flagsResolved && canManageNotificationRules) {
      items.push({
        value: "notify-rules",
        label: t("view-notification-rules") || "Notification rules",
      });
    }
    return items;
  }, [
    flagsResolved,
    canManageAlertRules,
    canManageNotificationRules,
    t,
  ]);

  const waitingForFlags =
    !flagsResolved &&
    (parsedView === "rules" || parsedView === "notify-rules");

  const controlValue = segmentData.some((s) => s.value === effectiveView)
    ? effectiveView
    : "notifications";

  const setView = (v: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("view", v);
    setSearchParams(next);
  };

  return (
    <DashboardLayout>
      <Stack gap="lg">
        <Group justify="center" w="100%">
          <SegmentedControl
            value={controlValue}
            onChange={setView}
            data={segmentData}
            fullWidth
            maw={720}
            size="sm"
          />
        </Group>
        {waitingForFlags ? (
          <Group justify="center" py="xl">
            <Loader />
          </Group>
        ) : (
          <>
            {effectiveView === "notifications" && <NotificationsInboxPage />}
            {effectiveView === "alerts" && <AlertsPage />}
            {effectiveView === "rules" && canManageAlertRules && <AlertRulesPage />}
            {effectiveView === "notify-rules" && canManageNotificationRules && (
              <NotificationSettingsPage />
            )}
          </>
        )}
      </Stack>
    </DashboardLayout>
  );
}
