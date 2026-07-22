import React, { useEffect, useState } from "react";
import { useStore } from "../../modules/store";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  getAllConversations,
  getUserOrganizations,
  getTags,
} from "../../modules/apiCalls";
import { useUnreadNotificationCount } from "../../hooks/useUnreadNotificationCount";
import { TConversation, TTag } from "../../types";
import { useTranslation } from "react-i18next";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";

import "./Sidebar.css";

import {
  Box,
  Button,
  ActionIcon,
  TextInput,
  NumberInput,
  Badge,
  Stack,
  Group,
  Text,
  Divider,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
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
  IconFilter,
  IconCalendarTime,
} from "@tabler/icons-react";

// ─── Main Sidebar ─────────────────────────────────────────────────────────────

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
  const { toggleSidebar, user, setOpenedModals, logout } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    user: state.user,
    setOpenedModals: state.setOpenedModals,
    logout: state.logout,
  }));

  const [history, setHistory] = useState<TConversation[]>([]);
  const [filteredHistory, setFilteredHistory] = useState<TConversation[]>([]);
  const [historyConfig, setHistoryConfig] = useState<{
    isOpen: boolean;
    showFilters: boolean;
  }>({
    isOpen: false,
    showFilters: false,
  });

  const [filters, setFilters] = useState<{
    tags: number[];
    startDate: Date | null;
    endDate: Date | null;
    title: string;
  }>({
    tags: [],
    startDate: null,
    endDate: null,
    title: "",
  });

  const [orgTags, setOrgTags] = useState<TTag[]>([]);
  const [canManageOrg, setCanManageOrg] = useState(false);
  const unreadNotificationCount = useUnreadNotificationCount();

  const navigate = useNavigate();

  useEffect(() => {
    let cancelled = false;
    getUserOrganizations()
      .then((orgs) => {
        if (!cancelled) {
          setCanManageOrg(orgs.some((o) => o.is_owner || o.can_manage));
        }
      })
      .catch(() => {
        if (!cancelled) setCanManageOrg(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    populateHistory();
    getTags()
      .then((tags) => setOrgTags(tags))
      .catch(() => setOrgTags([]));
  }, []);

  useEffect(() => {
    const refresh = () => populateHistory();
    window.addEventListener("conversations-changed", refresh);
    return () => window.removeEventListener("conversations-changed", refresh);
  }, []);

  useEffect(() => {
    let result = filterByDateRange();

    if (filters.tags.length > 0) {
      result = result.filter((c) =>
        c.tags?.some((tagId: number) => filters.tags.includes(tagId))
      );
    }

    result = result.filter(
      (c) =>
        c.title && c.title.toLowerCase().includes(filters.title.toLowerCase())
    );

    setFilteredHistory(result);
  }, [filters]);

  const populateHistory = async () => {
    const token = localStorage.getItem("token");
    if (!token) {
      console.error("No token found in localStorage");
      return;
    }

    try {
      const res = await getAllConversations("personal");
      setHistory(res);
      setFilteredHistory(res);
    } catch (error) {
      console.error("Failed to fetch conversations in sidebar", error);
    }
  };

  const handleNewChat = () => {
    toggleSidebar();
    navigate("/chat");
  };

  const goTo = (to: string) => {
    navigate(to);
    toggleSidebar();
  };

  const openSettings = () => {
    goTo("/settings");
  };

  const filterByDateRange = () => {
    return history.filter((c) => {
      const createdAtDate = new Date(c.created_at);

      const start = filters.startDate ? new Date(filters.startDate) : null;
      if (start) {
        start.setHours(0, 0, 0, 0);
      }

      const end = filters.endDate ? new Date(filters.endDate) : new Date();
      if (end) {
        end.setHours(23, 59, 59, 999);
      }

      return (!start || createdAtDate >= start) && createdAtDate <= end;
    });
  };

  const filterByTag = (tagId: number) => {
    setFilters((prev) => ({
      ...prev,
      tags: prev.tags.includes(tagId)
        ? prev.tags.filter((id) => id !== tagId)
        : [...prev.tags, tagId],
    }));
  };

  const today = new Date().toLocaleDateString();

  return (
    <>
      <div className="backdrop-blur-md fixed md:relative left-0 top-0 h-screen z-[50] md:z-[3] flex flex-col w-[min(350px,100%)] p-3 gap-2.5 animate-[appear-left_500ms_forwards] md:[animation:none]" style={{ background: "var(--semi-transparent)", borderRight: "1px solid var(--hovered-color)" }}>
        {/* Header */}
        <Group gap="xs">
          <Button
            variant="default"
            leftSection={<IconPlus size={20} />}
            onClick={handleNewChat}
            className="flex-1"
          >
            {t("new-chat")}
          </Button>
          <ActionIcon
            variant="default"
            size="lg"
            onClick={toggleSidebar}
            aria-label="Toggle sidebar"
          >
            <IconMenu2 size={20} />
          </ActionIcon>
        </Group>

        {/* Scrollable content */}
        <div className="[scrollbar-width:none] overflow-auto p-0.5 flex flex-col gap-2.5 flex-1">
          <Button
            variant="default"
            size="sm"
            leftSection={<IconMessage size={20} />}
            onClick={() =>
              setHistoryConfig((prev) => ({
                ...prev,
                isOpen: !prev.isOpen,
              }))
            }
            fullWidth
            styles={{
              root: {
                backgroundColor: historyConfig.isOpen
                  ? "rgba(255,255,255,0.08)"
                  : undefined,
              },
            }}
          >
            {t("conversations")}
          </Button>

          {historyConfig.isOpen && (
            <>
              {historyConfig.showFilters ? (
                <Stack gap="xs">
                  <TextInput
                    placeholder={t("filter-conversations")}
                    autoFocus
                    name="conversation-filter"
                    value={filters.title}
                    onChange={(e) => {
                      const val = e.currentTarget.value;
                      setFilters((prev) => ({ ...prev, title: val }));
                    }}
                    radius="md"
                    variant="filled"
                    size="xs"
                  />
                  <Group gap="xs" grow>
                    <DatePickerInput
                      value={filters.startDate}
                      onChange={(val) =>
                        setFilters({
                          ...filters,
                          startDate: val as Date | null,
                        })
                      }
                      placeholder={t("start-date")}
                      radius="md"
                      variant="filled"
                      clearable
                      size="xs"
                    />
                    <DatePickerInput
                      value={filters.endDate}
                      onChange={(val) =>
                        setFilters({
                          ...filters,
                          endDate: val as Date | null,
                        })
                      }
                      placeholder={t("end-date")}
                      radius="md"
                      variant="filled"
                      clearable
                      size="xs"
                    />
                  </Group>
                  <Group gap="xs" wrap="wrap">
                    {orgTags
                      .filter((tag) => tag.enabled)
                      .map((tag) => (
                        <Badge
                          key={tag.id}
                          variant={
                            filters.tags.includes(tag.id) ? "filled" : "outline"
                          }
                          color={tag.color || "violet"}
                          style={{ cursor: "pointer" }}
                          onClick={() => filterByTag(tag.id)}
                        >
                          {tag.title}
                        </Badge>
                      ))}
                  </Group>
                  <Divider />
                  <Group gap="xs" justify="flex-end">
                    <Button
                      size="xs"
                      variant="default"
                      onClick={() => {
                        setFilters({
                          tags: [],
                          startDate: null,
                          endDate: null,
                          title: "",
                        });
                      }}
                    >
                      {t("clean-filters")}
                    </Button>
                    <Button
                      size="xs"
                      variant="default"
                      onClick={() =>
                        setHistoryConfig((prev) => ({
                          ...prev,
                          showFilters: false,
                        }))
                      }
                    >
                      {t("close-filters")}
                    </Button>
                  </Group>
                </Stack>
              ) : (
                <Button
                  variant="default"
                  leftSection={<IconFilter size={18} />}
                  onClick={() =>
                    setHistoryConfig((prev) => ({
                      ...prev,
                      showFilters: true,
                    }))
                  }
                  fullWidth
                >
                  {t("show-filters")}
                </Button>
              )}

              <div className="h-full overflow-y-auto [scrollbar-width:none] flex flex-col gap-2.5">
                <Text size="sm" fw={600} c="white">
                  {t("today")}
                </Text>
                {filteredHistory
                  .filter(
                    (c) =>
                      new Date(c.created_at).toLocaleDateString() === today
                  )
                  .map((conversation) => (
                    <ConversationComponent
                      key={conversation.id}
                      conversation={conversation}
                    />
                  ))}
                <Text size="sm" fw={600} c="white">
                  {t("previous-days")}
                </Text>
                {filteredHistory
                  .filter(
                    (c) =>
                      new Date(c.created_at).toLocaleDateString() !== today
                  )
                  .map((conversation) => (
                    <ConversationComponent
                      key={conversation.id}
                      conversation={conversation}
                    />
                  ))}
              </div>
            </>
          )}

          {!historyConfig.isOpen && (
            <Stack gap="xs">
              <Button
                variant="default"
                leftSection={<IconCalendarTime size={20} />}
                onClick={() => goTo("/scheduled-tasks")}
                fullWidth
              >
                {t("scheduled-tasks-title")}
              </Button>
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
              {isConversationsDashboardEnabled && (
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
          )}
        </div>

        {/* Footer */}
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

      {/* Mobile backdrop */}
      <div
        onClick={toggleSidebar}
        className="bg-[rgba(55,55,55,0.52)] w-screen h-screen fixed top-0 left-0 z-[40] md:hidden"
      ></div>

    </>
  );
};

// ─── ConversationComponent ────────────────────────────────────────────────────

const ConversationComponent = ({
  conversation,
}: {
  conversation: TConversation;
}) => {
  const [_, setSearchParams] = useSearchParams();
  const { toggleSidebar, chatState } = useStore((state) => ({
    toggleSidebar: state.toggleSidebar,
    chatState: state.chatState,
  }));

  const navigate = useNavigate();

  const handleClick = () => {
    const queryParams = { conversation: conversation.id };
    setSearchParams(queryParams);
    navigate(`/chat?conversation=${conversation.id}`);

    if (window.innerWidth < 768 && chatState.isSidebarOpened) {
      toggleSidebar();
    }
  };

  return conversation.number_of_messages > 0 ? (
    <div
      className="sidebar-conversation-item flex items-center text-[17.5px] cursor-pointer relative text-ellipsis whitespace-nowrap p-0 rounded-lg transition-colors"
      onClick={handleClick}
    >
      <p className="w-full p-2.5 max-w-full overflow-hidden">
        {(conversation.title || conversation.id).slice(0, 30)}
      </p>
    </div>
  ) : null;
};
