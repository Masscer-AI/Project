import React from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { AppPage } from "../../components/AppPage/AppPage";
import AlertsPage from "./AlertsPage";
import AlertRulesPage from "./AlertRulesPage";
import NotificationSettingsPage from "./NotificationSettingsPage";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { Container, Group, Loader, Stack, Tabs } from "@mantine/core";

type AlertsHubView = "alerts" | "rules" | "notify-rules";

export default function AlertsHubPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const canViewAlerts = useIsFeatureEnabled("view-alerts");
  const canManageAlertRules = useIsFeatureEnabled("alert-rules-manager");

  if (canViewAlerts === null || canManageAlertRules === null) {
    return (
      <AppPage title={t("alerts")}>
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      </AppPage>
    );
  }

  const tabs: { value: AlertsHubView; label: string }[] = [
    ...(canViewAlerts
      ? [{ value: "alerts" as const, label: t("view-alerts-queue") }]
      : []),
    ...(canManageAlertRules
      ? [
          { value: "rules" as const, label: t("view-alert-rules") },
          { value: "notify-rules" as const, label: t("view-notification-rules") },
        ]
      : []),
  ];

  if (tabs.length === 0) {
    return <Navigate to="/notifications" replace />;
  }

  const requestedView = searchParams.get("view");
  const view =
    tabs.find((tab) => tab.value === requestedView)?.value ?? tabs[0].value;

  return (
    <AppPage title={t("alerts")}>
      <Container size="xl" py="xl">
        <Stack gap="lg">
          <Tabs
            value={view}
            onChange={(value) => {
              if (value) setSearchParams({ view: value });
            }}
          >
            <Tabs.List>
              {tabs.map((tab) => (
                <Tabs.Tab key={tab.value} value={tab.value}>
                  {tab.label}
                </Tabs.Tab>
              ))}
            </Tabs.List>
          </Tabs>
          {view === "alerts" && <AlertsPage />}
          {view === "rules" && <AlertRulesPage />}
          {view === "notify-rules" && <NotificationSettingsPage />}
        </Stack>
      </Container>
    </AppPage>
  );
}
