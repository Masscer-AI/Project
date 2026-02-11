import React from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useTranslation } from "react-i18next";
import { useNavigate, useLocation } from "react-router-dom";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { ActionIcon, Container, Tabs } from "@mantine/core";
import {
  IconMenu2,
  IconChartBar,
  IconBell,
  IconShield,
  IconHash,
} from "@tabler/icons-react";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

interface DashboardTab {
  value: string;
  icon: typeof IconChartBar;
  labelKey: string;
  featureFlag?: string;
}

const TABS: DashboardTab[] = [
  { value: "/dashboard", icon: IconChartBar, labelKey: "overview" },
  { value: "/dashboard/alerts", icon: IconBell, labelKey: "alerts" },
  {
    value: "/dashboard/alert-rules",
    icon: IconShield,
    labelKey: "alert-rules",
    featureFlag: "alert-rules-manager",
  },
  {
    value: "/dashboard/tags",
    icon: IconHash,
    labelKey: "manage-tags",
    featureFlag: "tags-management",
  },
];

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const { chatState, toggleSidebar } = useStore((state) => ({
    chatState: state.chatState,
    toggleSidebar: state.toggleSidebar,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();

  const canManageAlertRules = useIsFeatureEnabled("alert-rules-manager");
  const canManageTags = useIsFeatureEnabled("tags-management");

  const featureFlagMap: Record<string, boolean | null> = {
    "alert-rules-manager": canManageAlertRules,
    "tags-management": canManageTags,
  };

  const currentTab =
    TABS.find((tab) => tab.value === location.pathname)?.value || "/dashboard";

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          minHeight: "100vh",
          position: "relative",
        }}
      >
        {!chatState.isSidebarOpened && (
          <div style={{ position: "absolute", top: 24, left: 24, zIndex: 10 }}>
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={toggleSidebar}
            >
              <IconMenu2 size={20} />
            </ActionIcon>
          </div>
        )}

        <Container size="xl" py="xl">
          <Tabs
            value={currentTab}
            onChange={(value) => {
              if (value) navigate(value);
            }}
            variant="outline"
            mb="lg"
          >
            <Tabs.List justify="center">
              {TABS.map((tab) => {
                const flag = (tab as DashboardTab).featureFlag;
                if (flag && featureFlagMap[flag] === false) {
                  return null;
                }
                const Icon = tab.icon;
                return (
                  <Tabs.Tab
                    key={tab.value}
                    value={tab.value}
                    leftSection={<Icon size={16} />}
                  >
                    {t(tab.labelKey) || tab.labelKey}
                  </Tabs.Tab>
                );
              })}
            </Tabs.List>
          </Tabs>

          {children}
        </Container>
      </div>
    </main>
  );
}
