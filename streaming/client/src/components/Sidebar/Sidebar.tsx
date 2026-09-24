import React, { useEffect, useState } from "react";
import { useStore } from "../../modules/store";
import { Link, useLocation } from "react-router-dom";
import { getUserOrganizations } from "../../modules/apiCalls";
import { useUnreadNotificationCount } from "../../hooks/useUnreadNotificationCount";
import { useTranslation } from "react-i18next";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";

import "./Sidebar.css";

import {
  Box,
  Button,
  ActionIcon,
  Badge,
  Stack,
  Group,
} from "@mantine/core";
import {
  IconPlus,
  IconMenu2,
  IconMessage,
  IconWaveSine,
  IconDatabase,
  IconPuzzle,
  IconPlugConnected,
  IconBrandWhatsapp,
  IconBuilding,
  IconLayoutDashboard,
  IconSettings,
  IconLogout,
  IconCalendarTime,
  IconPhoto,
  IconScale,
} from "@tabler/icons-react";

function NavButton({
  to,
  children,
  leftSection,
  size,
  className,
  fullWidth = true,
  active,
}: {
  to: string;
  children: React.ReactNode;
  leftSection?: React.ReactNode;
  size?: "sm";
  className?: string;
  fullWidth?: boolean;
  active?: boolean;
}) {
  const toggleSidebar = useStore((s) => s.toggleSidebar);
  return (
    <Button
      component={Link}
      to={to}
      variant="default"
      leftSection={leftSection}
      size={size}
      fullWidth={fullWidth}
      className={className}
      onClick={toggleSidebar}
      styles={{
        root: {
          backgroundColor: active ? "rgba(255,255,255,0.08)" : undefined,
        },
      }}
    >
      {children}
    </Button>
  );
}

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const isConversationsDashboardEnabled = useIsFeatureEnabled(
    "conversations-dashboard"
  );
  const isChatWidgetsEnabled = useIsFeatureEnabled("chat-widgets-management");
  const isIntegrationsEnabled = useIsFeatureEnabled("can-manage-integrations");
  const isWhatsappNumbersManagementEnabled = useIsFeatureEnabled(
    "whatsapp-numbers-management"
  );
  const isTrainAgentsEnabled = useIsFeatureEnabled("train-agents");
  const isAudioToolsEnabled = useIsFeatureEnabled("audio-tools");
  const canEditPreferences = useIsFeatureEnabled("can-edit-preferences") === true;
  const canUseChat = useIsFeatureEnabled("can-use-chat") === true;
  const hasOrgComplianceAccess =
    useIsFeatureEnabled("organization-compliance-access") === true;
  const { toggleSidebar, user, logout } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    user: state.user,
    logout: state.logout,
  }));
  const [hasPldAccess, setHasPldAccess] = useState(false);
  const [hasOrganization, setHasOrganization] = useState<boolean | null>(null);
  const location = useLocation();

  const [canManageOrg, setCanManageOrg] = useState(false);
  const unreadNotificationCount = useUnreadNotificationCount();

  useEffect(() => {
    let cancelled = false;
    getUserOrganizations()
      .then((orgs) => {
        if (!cancelled) {
          setCanManageOrg(orgs.some((o) => o.is_owner || o.can_manage));
          setHasPldAccess(orgs.some((o) => o.pld_access_enabled));
          setHasOrganization(orgs.length > 0);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCanManageOrg(false);
          setHasPldAccess(false);
          setHasOrganization(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const navActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  return (
    <>
      <div className="backdrop-blur-md fixed md:relative left-0 top-0 h-screen z-[50] md:z-[3] flex flex-col w-[min(350px,100%)] max-w-full shrink-0 min-w-0 p-3 gap-2.5 animate-[appear-left_500ms_forwards] md:[animation:none]" style={{ background: "var(--semi-transparent)", borderRight: "1px solid var(--hovered-color)" }}>
        <Group gap="xs">
          {canUseChat && (
            <Button
              variant="default"
              leftSection={<IconPlus size={20} />}
              onClick={handleNewChat}
              className="flex-1"
            >
              {t("new-chat")}
            </Button>
          )}
          <ActionIcon
            variant="default"
            size="lg"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            <IconMenu2 size={20} />
          </ActionIcon>
        </Group>

        <div className="[scrollbar-width:none] overflow-auto p-0.5 flex flex-col gap-2.5 flex-1">
          {canUseChat && (
            <Button
              variant="default"
              size="sm"
              leftSection={<IconMessage size={20} />}
              onClick={() => goTo("/conversations")}
              fullWidth
              styles={{
                root: {
                  backgroundColor: navActive("/conversations")
                    ? "rgba(255,255,255,0.08)"
                    : undefined,
                },
              }}
            >
              {t("conversations")}
            </Button>
          )}
          {!canUseChat && hasOrganization === false && (
            <Button
              variant="default"
              size="sm"
              leftSection={<IconScale size={20} />}
              onClick={() => goTo("/pld/expediente")}
              fullWidth
              styles={{
                root: {
                  backgroundColor: navActive("/pld")
                    ? "rgba(255,255,255,0.08)"
                    : undefined,
                },
              }}
            >
              {t("compliance-my-expediente-title")}
            </Button>
          )}
          {hasOrgComplianceAccess && hasPldAccess && (
            <Button
              variant="default"
              size="sm"
              leftSection={<IconScale size={20} />}
              onClick={() => goTo("/compliance")}
              fullWidth
              styles={{
                root: {
                  backgroundColor: navActive("/compliance")
                    ? "rgba(255,255,255,0.08)"
                    : undefined,
                },
              }}
            >
              {t("compliance-nav")}
            </Button>
          )}

          <Stack gap="xs">
              {canUseChat && (
                <Button
                  variant="default"
                  leftSection={<IconCalendarTime size={20} />}
                  onClick={() => goTo("/scheduled-tasks")}
                  fullWidth
                >
                  {t("scheduled-tasks-title")}
                </Button>
              )}
              {canUseChat && (
                <Button
                  variant="default"
                  leftSection={<IconPhoto size={20} />}
                  onClick={() => goTo("/gallery")}
                  fullWidth
                >
                  {t("gallery-title")}
                </Button>
              )}
              {isAudioToolsEnabled && (
                <Button
                  variant="default"
                  leftSection={<IconWaveSine size={20} />}
                  onClick={() => goTo("/generation-tools")}
                  fullWidth
                >
                  {t("audio-tools")}
                </Button>
              )}
              {isWhatsappNumbersManagementEnabled && (
                <Button
                  variant="default"
                  leftSection={<IconBrandWhatsapp size={20} />}
                  onClick={() => goTo("/whatsapp")}
                  fullWidth
                >
                  {t("whatsapp")}
                </Button>
              )}
              {isTrainAgentsEnabled && (
                <Button
                  variant="default"
                  leftSection={<IconDatabase size={20} />}
                  onClick={() => goTo("/knowledge-base")}
                  fullWidth
                >
                  {t("knowledge-base")}
                </Button>
              )}
              {isChatWidgetsEnabled && (
                <Button
                  variant="default"
                  leftSection={<IconPuzzle size={20} />}
                  onClick={() => goTo("/chat-widgets")}
                  fullWidth
                >
                  {t("chat-widgets")}
                </Button>
              )}
              {isIntegrationsEnabled && (
                <Button
                  variant="default"
                  leftSection={<IconPlugConnected size={20} />}
                  onClick={() => goTo("/integrations")}
                  fullWidth
                >
                  {t("integrations-title")}
                </Button>
              )}
              {canManageOrg && (
                <Button
                  variant="default"
                  leftSection={<IconBuilding size={20} />}
                  onClick={() => goTo("/organization")}
                  fullWidth
                >
                  {t("manage-organization")}
                </Button>
              )}
              {canUseChat && isConversationsDashboardEnabled && (
                <Box pos="relative">
                  <Button
                    variant="default"
                    leftSection={<IconLayoutDashboard size={20} />}
                    onClick={() => goTo("/dashboard")}
                    fullWidth
                  >
                    {t("conversations-dashboard")}
                  </Button>
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
                      {unreadNotificationCount > 99
                        ? "99+"
                        : unreadNotificationCount}
                    </Badge>
                  )}
                </Box>
              )}
            </Stack>
        </div>

        <Group gap="xs" className="mt-auto">
          <Button
            variant="default"
            leftSection={
              canEditPreferences ? <IconSettings size={20} /> : undefined
            }
            onClick={canEditPreferences ? openSettings : undefined}
            disabled={!canEditPreferences}
            className="flex-1"
          >
            {user ? user.username : t("you")}
          </Button>
          <ActionIcon
            variant="default"
            size="lg"
            onClick={logout}
            aria-label={t("logout")}
          >
            <IconLogout size={20} />
          </ActionIcon>
        </Group>
      </div>

      <div
        onClick={toggleSidebar}
        className="bg-[rgba(55,55,55,0.52)] w-screen h-screen fixed top-0 left-0 z-[40] md:hidden"
      ></div>
    </>
  );
};
