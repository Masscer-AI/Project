import React, { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ActionIcon, Avatar, Badge, Menu, Tooltip } from "@mantine/core";
import { useMediaQuery } from "@mantine/hooks";
import {
  IconPlus,
  IconMessage,
  IconWaveSine,
  IconDatabase,
  IconPuzzle,
  IconPlugConnected,
  IconBrandWhatsapp,
  IconBuilding,
  IconSettings,
  IconLogout,
  IconCalendarTime,
  IconPhoto,
  IconScale,
  IconSearch,
  IconLayoutSidebarLeftCollapse,
  IconChartBar,
  IconChevronDown,
  IconChevronRight,
} from "@tabler/icons-react";
import { getUserOrganizations } from "../../modules/apiCalls";
import { API_URL } from "../../modules/constants";
import { useUnreadNotificationCount } from "../../hooks/useUnreadNotificationCount";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { useStore } from "../../modules/store";
import type { TOrganization } from "../../types";
import "./Sidebar.css";

type NavItemDef = {
  to: string;
  label: string;
  icon: React.ReactNode;
  match?: string;
  badge?: number;
};

function brandInitial(name: string) {
  return (name.trim()[0] || "M").toUpperCase();
}

function NavItem({
  item,
  collapsed,
  active,
  onNavigate,
}: {
  item: NavItemDef;
  collapsed: boolean;
  active: boolean;
  onNavigate: () => void;
}) {
  const badge =
    item.badge && item.badge > 0 ? (
      <Badge
        color="red"
        size="sm"
        radius="xl"
        variant="filled"
        styles={{ root: { pointerEvents: "none", minWidth: 18, padding: "0 5px" } }}
      >
        {item.badge > 99 ? "99+" : item.badge}
      </Badge>
    ) : null;

  const link = (
    <Link
      to={item.to}
      className={`app-sidebar-link${active ? " app-sidebar-link--active" : ""}`}
      onClick={onNavigate}
      aria-label={collapsed ? item.label : undefined}
    >
      <span className="app-sidebar-link-icon">{item.icon}</span>
      {!collapsed && <span className="app-sidebar-link-label">{item.label}</span>}
      {!collapsed && badge}
      {collapsed && badge ? (
        <Badge
          color="red"
          size="xs"
          radius="xl"
          variant="filled"
          pos="absolute"
          top={2}
          right={2}
          styles={{ root: { pointerEvents: "none", minWidth: 14, padding: "0 3px" } }}
        >
          {item.badge && item.badge > 99 ? "99+" : item.badge}
        </Badge>
      ) : null}
    </Link>
  );

  if (!collapsed) return link;
  return (
    <Tooltip label={item.label} position="right" withArrow>
      <div>{link}</div>
    </Tooltip>
  );
}

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const isDesktop = useMediaQuery("(min-width: 48em)");
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
  const toggleSidebar = useStore((s) => s.toggleSidebar);
  const toggleSidebarCollapsed = useStore((s) => s.toggleSidebarCollapsed);
  const isSidebarOpened = useStore((s) => s.chatState.isSidebarOpened);
  const sidebarCollapsed = useStore((s) => s.chatState.sidebarCollapsed);
  const user = useStore((s) => s.user);
  const logout = useStore((s) => s.logout);
  const tenantBranding = useStore((s) => s.tenantBranding);
  const [hasPldAccess, setHasPldAccess] = useState(false);
  const [hasOrganization, setHasOrganization] = useState<boolean | null>(null);
  const [canManageOrg, setCanManageOrg] = useState(false);
  const [org, setOrg] = useState<TOrganization | null>(null);
  const [adminOpen, setAdminOpen] = useState(true);
  const location = useLocation();
  const unreadNotificationCount = useUnreadNotificationCount();
  const collapsed = Boolean(isDesktop && sidebarCollapsed);

  useEffect(() => {
    let cancelled = false;
    getUserOrganizations()
      .then((orgs) => {
        if (cancelled) return;
        setCanManageOrg(orgs.some((o) => o.is_owner || o.can_manage));
        setHasPldAccess(orgs.some((o) => o.pld_access_enabled));
        setHasOrganization(orgs.length > 0);
        setOrg(
          orgs.find((o) => o.is_owner || o.can_manage) || orgs[0] || null
        );
      })
      .catch(() => {
        if (cancelled) return;
        setCanManageOrg(false);
        setHasPldAccess(false);
        setHasOrganization(null);
        setOrg(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const navActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(`${path}/`);

  const onNavigate = () => {
    if (!isDesktop && isSidebarOpened) toggleSidebar();
  };

  const brandName =
    org?.name?.trim() ||
    tenantBranding?.app_name?.trim() ||
    "Masscer";
  const brandLogo = org?.logo_url
    ? `${API_URL}${org.logo_url}`
    : tenantBranding?.logo_url
      ? `${API_URL}${tenantBranding.logo_url}`
      : null;
  const displayName = user?.profile?.name || user?.username || t("you");
  const userInitial = brandInitial(displayName);
  const iconSize = 18;

  const mainItems: NavItemDef[] = [
    canUseChat && {
      to: "/conversations",
      label: t("conversations"),
      icon: <IconMessage size={iconSize} />,
    },
    isTrainAgentsEnabled && {
      to: "/knowledge-base",
      label: t("knowledge-base"),
      icon: <IconDatabase size={iconSize} />,
    },
    canUseChat && {
      to: "/gallery",
      label: t("gallery-title"),
      icon: <IconPhoto size={iconSize} />,
    },
    isAudioToolsEnabled && {
      to: "/generation-tools",
      label: t("audio-tools"),
      icon: <IconWaveSine size={iconSize} />,
    },
    canUseChat && {
      to: "/scheduled-tasks",
      label: t("scheduled-tasks-title"),
      icon: <IconCalendarTime size={iconSize} />,
    },
    !canUseChat &&
      hasOrganization === false && {
        to: "/pld/expediente",
        label: t("compliance-my-expediente-title"),
        icon: <IconScale size={iconSize} />,
        match: "/pld",
      },
  ].filter(Boolean) as NavItemDef[];

  const channelItems: NavItemDef[] = [
    isWhatsappNumbersManagementEnabled && {
      to: "/whatsapp",
      label: t("whatsapp"),
      icon: <IconBrandWhatsapp size={iconSize} />,
    },
    isChatWidgetsEnabled && {
      to: "/chat-widgets",
      label: t("chat-widgets"),
      icon: <IconPuzzle size={iconSize} />,
    },
    isIntegrationsEnabled && {
      to: "/integrations",
      label: t("integrations-title"),
      icon: <IconPlugConnected size={iconSize} />,
    },
  ].filter(Boolean) as NavItemDef[];

  const adminItems: NavItemDef[] = [
    canUseChat &&
      isConversationsDashboardEnabled && {
        to: "/dashboard",
        label: t("sidebar-analytics"),
        icon: <IconChartBar size={iconSize} />,
        badge: unreadNotificationCount,
      },
    hasOrgComplianceAccess &&
      hasPldAccess && {
        to: "/compliance",
        label: t("compliance-nav"),
        icon: <IconScale size={iconSize} />,
      },
    canManageOrg && {
      to: "/organization",
      label: t("manage-organization"),
      icon: <IconBuilding size={iconSize} />,
    },
  ].filter(Boolean) as NavItemDef[];

  const showAdmin = adminOpen || collapsed;
  const collapseLabel = collapsed
    ? t("expand-sidebar")
    : t("collapse-sidebar");

  const settingsItem = canEditPreferences ? (
    <Menu.Item
      leftSection={<IconSettings size={16} />}
      component={Link}
      to="/settings"
      onClick={onNavigate}
    >
      {t("settings")}
    </Menu.Item>
  ) : null;

  const userMenu = (
    <Menu shadow="md" width={200} position={collapsed ? "right-end" : "top"}>
      <Menu.Target>
        <button type="button" className="app-sidebar-user" aria-label={displayName}>
          <Avatar
            src={user?.profile?.avatar_url || undefined}
            size={28}
            radius="xl"
            color="green"
          >
            {userInitial}
          </Avatar>
          {!collapsed && (
            <>
              <span className="app-sidebar-user-copy">
                <span className="app-sidebar-user-name">{displayName}</span>
                {user?.email ? (
                  <span className="app-sidebar-user-email">{user.email}</span>
                ) : null}
              </span>
              <IconChevronDown size={14} />
            </>
          )}
        </button>
      </Menu.Target>
      <Menu.Dropdown>
        {settingsItem}
        <Menu.Item
          color="red"
          leftSection={<IconLogout size={16} />}
          onClick={logout}
        >
          {t("logout")}
        </Menu.Item>
      </Menu.Dropdown>
    </Menu>
  );

  return (
    <>
      <aside
        className={`app-sidebar${collapsed ? " app-sidebar--collapsed" : ""}${
          isSidebarOpened ? " app-sidebar--open" : ""
        }`}
      >
        <div className="app-sidebar-brand">
          {collapsed ? (
            <Tooltip label={collapseLabel} position="right" withArrow>
              <button
                type="button"
                className="app-sidebar-mark"
                onClick={toggleSidebarCollapsed}
                aria-label={collapseLabel}
                style={{ border: "none", cursor: "pointer" }}
              >
                {brandLogo ? <img src={brandLogo} alt="" /> : brandInitial(brandName)}
              </button>
            </Tooltip>
          ) : (
            <>
              <div className="app-sidebar-mark">
                {brandLogo ? <img src={brandLogo} alt="" /> : brandInitial(brandName)}
              </div>
              <span className="app-sidebar-brand-text">{brandName}</span>
              {isDesktop && (
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  size="sm"
                  onClick={toggleSidebarCollapsed}
                  aria-label={collapseLabel}
                >
                  <IconLayoutSidebarLeftCollapse size={16} />
                </ActionIcon>
              )}
            </>
          )}
        </div>

        {canUseChat && (
          <div className="app-sidebar-newchat">
            {collapsed ? (
              <Tooltip label={t("new-chat")} position="right" withArrow>
                <Link
                  to="/chat"
                  className="app-sidebar-newchat-btn"
                  onClick={onNavigate}
                  aria-label={t("new-chat")}
                >
                  <IconPlus size={18} />
                </Link>
              </Tooltip>
            ) : (
              <>
                <Link
                  to="/chat"
                  className="app-sidebar-newchat-btn"
                  onClick={onNavigate}
                >
                  <IconPlus size={16} />
                  {t("new-chat")}
                </Link>
                <Tooltip label={t("search-conversations")} withArrow>
                  <ActionIcon
                    className="app-sidebar-search"
                    variant="subtle"
                    color="gray"
                    component={Link}
                    to="/conversations"
                    onClick={onNavigate}
                    aria-label={t("search-conversations")}
                  >
                    <IconSearch size={18} />
                  </ActionIcon>
                </Tooltip>
              </>
            )}
          </div>
        )}

        <nav className="app-sidebar-nav">
          {mainItems.map((item) => (
            <NavItem
              key={item.to}
              item={item}
              collapsed={collapsed}
              active={navActive(item.match || item.to)}
              onNavigate={onNavigate}
            />
          ))}

          {channelItems.length > 0 && (
            <>
              {!collapsed && (
                <div className="app-sidebar-section-label">{t("sidebar-channels")}</div>
              )}
              {channelItems.map((item) => (
                <NavItem
                  key={item.to}
                  item={item}
                  collapsed={collapsed}
                  active={navActive(item.to)}
                  onNavigate={onNavigate}
                />
              ))}
            </>
          )}

          {adminItems.length > 0 && (
            <>
              {!collapsed && (
                <button
                  type="button"
                  className="app-sidebar-admin-toggle"
                  onClick={() => setAdminOpen((open) => !open)}
                >
                  <span className="app-sidebar-section-label">{t("sidebar-admin")}</span>
                  {adminOpen ? (
                    <IconChevronDown size={14} />
                  ) : (
                    <IconChevronRight size={14} />
                  )}
                </button>
              )}
              {showAdmin &&
                adminItems.map((item) => (
                  <NavItem
                    key={item.to}
                    item={item}
                    collapsed={collapsed}
                    active={navActive(item.to)}
                    onNavigate={onNavigate}
                  />
                ))}
            </>
          )}
        </nav>

        <div className="app-sidebar-footer">
          {collapsed && canEditPreferences && (
            <Tooltip label={t("settings")} position="right" withArrow>
              <ActionIcon
                variant="subtle"
                color="gray"
                component={Link}
                to="/settings"
                onClick={onNavigate}
                aria-label={t("settings")}
              >
                <IconSettings size={18} />
              </ActionIcon>
            </Tooltip>
          )}
          {collapsed ? (
            <Tooltip label={displayName} position="right" withArrow>
              <div>{userMenu}</div>
            </Tooltip>
          ) : (
            userMenu
          )}
        </div>
      </aside>

      {!isDesktop && isSidebarOpened && (
        <div onClick={toggleSidebar} className="app-sidebar-backdrop" />
      )}
    </>
  );
};
