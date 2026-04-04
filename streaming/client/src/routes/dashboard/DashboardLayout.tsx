import React from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useTranslation } from "react-i18next";
import { useNavigate, useLocation } from "react-router-dom";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import {
  formatUnreadNotificationBadge,
  useUnreadNotificationCount,
} from "../../hooks/useUnreadNotificationCount";
import { ActionIcon, Badge, Box, Container, Group, Tabs } from "@mantine/core";
import {
  IconMenu2,
  IconChartBar,
  IconHash,
  IconBellRinging,
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
  {
    value: "/dashboard/alerts",
    icon: IconBellRinging,
    labelKey: "alerts-hub",
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
  const unreadNotificationCount = useUnreadNotificationCount();

  const canManageTags = useIsFeatureEnabled("tags-management");

  const featureFlagMap: Record<string, boolean | null> = {
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
            <Box pos="relative" style={{ display: "inline-block" }}>
              <ActionIcon
                variant="subtle"
                color="gray"
                onClick={toggleSidebar}
                aria-label={t("open-sidebar") || "Open menu"}
              >
                <IconMenu2 size={20} />
              </ActionIcon>
              {unreadNotificationCount > 0 && (
                <Badge
                  color="red"
                  size="sm"
                  radius="xl"
                  variant="filled"
                  pos="absolute"
                  top={-4}
                  right={-4}
                  styles={{ root: { pointerEvents: "none", minWidth: 20 } }}
                >
                  {formatUnreadNotificationBadge(unreadNotificationCount)}
                </Badge>
              )}
            </Box>
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
                const flag = tab.featureFlag;
                const flagEnabled = flag ? featureFlagMap[flag] : true;
                const hideForFlag = flagEnabled === false;
                const stillResolving = flagEnabled === null;
                if (hideForFlag && !stillResolving) {
                  return null;
                }
                const Icon = tab.icon;
                const showAlertsBadge =
                  tab.value === "/dashboard/alerts" && unreadNotificationCount > 0;
                return (
                  <Tabs.Tab
                    key={tab.value}
                    value={tab.value}
                    leftSection={<Icon size={16} />}
                  >
                    <Group gap={6} wrap="nowrap" justify="center">
                      <span>{t(tab.labelKey) || tab.labelKey}</span>
                      {showAlertsBadge && (
                        <Badge
                          color="red"
                          size="xs"
                          radius="xl"
                          variant="filled"
                          styles={{ root: { minWidth: 18 } }}
                        >
                          {formatUnreadNotificationBadge(unreadNotificationCount)}
                        </Badge>
                      )}
                    </Group>
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
