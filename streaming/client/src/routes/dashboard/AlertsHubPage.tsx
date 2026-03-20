import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { DashboardLayout } from "./DashboardLayout";
import AlertsPage from "./AlertsPage";
import AlertRulesPage from "./AlertRulesPage";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { Group, SegmentedControl, Stack } from "@mantine/core";

/**
 * Alerts queue + alert rules in one place. ?view=list (default) | ?view=rules
 * Preserves other query params (e.g. conversation).
 */
export default function AlertsHubPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const view = searchParams.get("view") === "rules" ? "rules" : "list";
  const canManageAlertRules = useIsFeatureEnabled("alert-rules-manager");
  const flagsResolved = canManageAlertRules !== null;

  useEffect(() => {
    if (!flagsResolved || view !== "rules") return;
    if (canManageAlertRules === false) {
      const next = new URLSearchParams(searchParams);
      next.delete("view");
      setSearchParams(next, { replace: true });
    }
  }, [flagsResolved, canManageAlertRules, view, searchParams, setSearchParams]);

  const setView = (v: string) => {
    const next = new URLSearchParams(searchParams);
    if (v === "list") {
      next.delete("view");
    } else {
      next.set("view", "rules");
    }
    setSearchParams(next);
  };

  const showRulesToggle = flagsResolved && canManageAlertRules === true;

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
                  value: "list",
                  label: t("view-alerts-queue") || "Alerts",
                },
                {
                  value: "rules",
                  label: t("view-alert-rules") || "Alert rules",
                },
              ]}
            />
          </Group>
        )}
        {view === "list" ? <AlertsPage /> : <AlertRulesPage />}
      </Stack>
    </DashboardLayout>
  );
}
