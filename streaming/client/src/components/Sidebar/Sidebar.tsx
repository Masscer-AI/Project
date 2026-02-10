import React, { useEffect, useState } from "react";
import { SVGS } from "../../assets/svgs";
import { useStore } from "../../modules/store";
import { useSearchParams, useNavigate } from "react-router-dom";
import {
  deleteConversation,
  generateTrainingCompletions,
  getAllConversations,
  getUserOrganizations,
  shareConversation,
} from "../../modules/apiCalls";
import { TConversation } from "../../types";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { QRCodeDisplay } from "../QRGenerator/QRGenerator";

import "./Sidebar.css";

import {
  Button,
  ActionIcon,
  TextInput,
  NumberInput,
  Badge,
  Modal,
  Menu,
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
  IconBuilding,
  IconLayoutDashboard,
  IconSettings,
  IconLogout,
  IconDotsVertical,
  IconTrash,
  IconBarbell,
  IconShare,
  IconCopy,
  IconExternalLink,
  IconFilter,
} from "@tabler/icons-react";

// ─── Main Sidebar ─────────────────────────────────────────────────────────────

export const Sidebar: React.FC = () => {
  const { t } = useTranslation();
  const isConversationsDashboardEnabled = useIsFeatureEnabled(
    "conversations-dashboard"
  );
  const isChatWidgetsEnabled = useIsFeatureEnabled("chat-widgets-management");
  const isTrainAgentsEnabled = useIsFeatureEnabled("train-agents");
  const isAudioToolsEnabled = useIsFeatureEnabled("audio-tools");
  const { toggleSidebar, setConversation, user, setOpenedModals, logout, userTags } =
    useStore((state) => ({
      toggleSidebar: state.toggleSidebar,
      setConversation: state.setConversation,
      user: state.user,
      setOpenedModals: state.setOpenedModals,
      logout: state.logout,
      userTags: state.userTags,
    }));

  const [history, setHistory] = useState<TConversation[]>([]);
  const [filteredHistory, setFilteredHistory] = useState<TConversation[]>([]);
  const [searchParams, setSearchParams] = useSearchParams();
  const [historyConfig, setHistoryConfig] = useState<{
    isOpen: boolean;
    showFilters: boolean;
  }>({
    isOpen: false,
    showFilters: false,
  });

  const [filters, setFilters] = useState<{
    tags: string[];
    startDate: Date | null;
    endDate: Date | null;
    title: string;
  }>({
    tags: [],
    startDate: null,
    endDate: null,
    title: "",
  });

  const [canManageOrg, setCanManageOrg] = useState(false);

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
  }, []);

  useEffect(() => {
    let result = filterByDateRange();

    if (filters.tags.length > 0) {
      result = result.filter((c) =>
        c.tags?.some((tag: number) => filters.tags.includes(tag.toString()))
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
      const res = await getAllConversations();
      setHistory(res);
      setFilteredHistory(res);
    } catch (error) {
      console.error("Failed to fetch conversations in sidebar", error);
    }
  };

  const handleNewChat = () => {
    setConversation(null);
    if (searchParams.has("conversation")) {
      searchParams.delete("conversation");
      setSearchParams(searchParams);
    }
    toggleSidebar();
    navigate(`/chat`);
  };

  const goTo = (to: string) => {
    navigate(to);
    toggleSidebar();
  };

  const deleteConversationItem = async (id: string) => {
    setHistory(history.filter((conversation) => conversation.id !== id));
    setFilteredHistory(
      filteredHistory.filter((conversation) => conversation.id !== id)
    );
    await deleteConversation(id);
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

  const filterByTag = (tag: string) => {
    setFilters((prev) => ({
      ...prev,
      tags: prev.tags.includes(tag)
        ? prev.tags.filter((t) => t !== tag)
        : [...prev.tags, tag],
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
                    {userTags.map((tag) => (
                      <Badge
                        key={tag}
                        variant={
                          filters.tags.includes(tag) ? "filled" : "default"
                        }
                        style={{ cursor: "pointer" }}
                        onClick={() => filterByTag(tag)}
                      >
                        {tag}
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
                      deleteConversationItem={deleteConversationItem}
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
                      deleteConversationItem={deleteConversationItem}
                    />
                  ))}
              </div>
            </>
          )}

          {!historyConfig.isOpen && (
            <Stack gap="xs">
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
              {/* WhatsApp — disabled until feature is complete
              <Button
                variant="default"
                leftSection={
                  <div className="w-5 h-5 flex items-center justify-center [&>svg]:w-5 [&>svg]:h-5">
                    {SVGS.whatsapp}
                  </div>
                }
                onClick={() => goTo("/whatsapp")}
                fullWidth
              >
                {t("whatsapp")}
              </Button>
              */}
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
                <Button
                  variant="default"
                  leftSection={<IconLayoutDashboard size={20} />}
                  onClick={() => goTo("/dashboard")}
                  fullWidth
                >
                  {t("conversations-dashboard")}
                </Button>
              )}
            </Stack>
          )}
        </div>

        {/* Footer */}
        <Group gap="xs" className="mt-auto">
          <Button
            variant="default"
            leftSection={<IconSettings size={20} />}
            onClick={openSettings}
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
  deleteConversationItem,
}: {
  conversation: TConversation;
  deleteConversationItem: (id: string) => void;
}) => {
  const [_, setSearchParams] = useSearchParams();
  const { setConversation, toggleSidebar, chatState } = useStore((state) => ({
    setConversation: state.setConversation,
    toggleSidebar: state.toggleSidebar,
    chatState: state.chatState,
  }));

  const { t } = useTranslation();
  const isTrainAgentsEnabled = useIsFeatureEnabled("train-agents");
  const [showTrainingModal, setShowTrainingModal] = useState(false);
  const [showShareModal, setShowShareModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const navigate = useNavigate();

  const handleClick = () => {
    setConversation(conversation.id);
    const queryParams = { conversation: conversation.id };
    setSearchParams(queryParams);
    navigate(`/chat?conversation=${conversation.id}`);

    // Close sidebar on mobile after selecting a conversation
    if (window.innerWidth < 768 && chatState.isSidebarOpened) {
      toggleSidebar();
    }
  };

  return conversation.number_of_messages > 0 ? (
    <div className="sidebar-conversation-item flex items-center justify-between text-[17.5px] cursor-pointer relative text-ellipsis whitespace-nowrap p-0 rounded-lg transition-colors">
      <p
        className="w-full p-2.5 max-w-full overflow-hidden"
        onClick={handleClick}
      >
        {(conversation.title || conversation.id).slice(0, 30)}
      </p>

      <ShareConversationModal
        opened={showShareModal}
        onClose={() => setShowShareModal(false)}
        conversationId={conversation.id}
      />
      <TrainingOnConversation
        opened={showTrainingModal}
        onClose={() => setShowTrainingModal(false)}
        conversation={conversation}
      />
      <Modal
        opened={showDeleteConfirm}
        onClose={() => setShowDeleteConfirm(false)}
        title={t("delete-conversation")}
        size="sm"
        centered
      >
        <Text size="sm" mb="md">
          {t("sure")}?
        </Text>
        <Group justify="flex-end" gap="xs">
          <Button variant="default" onClick={() => setShowDeleteConfirm(false)}>
            {t("cancel")}
          </Button>
          <Button
            color="red"
            onClick={() => {
              deleteConversationItem(conversation.id);
              setShowDeleteConfirm(false);
            }}
          >
            {t("delete")}
          </Button>
        </Group>
      </Modal>

      <Menu position="left-start" withArrow shadow="md">
        <Menu.Target>
          <ActionIcon variant="subtle" color="gray" size="sm">
            <IconDotsVertical size={18} />
          </ActionIcon>
        </Menu.Target>
        <Menu.Dropdown>
          <Menu.Item
            color="red"
            leftSection={<IconTrash size={16} />}
            onClick={() => setShowDeleteConfirm(true)}
          >
            {t("delete")}
          </Menu.Item>
          {isTrainAgentsEnabled && (
            <Menu.Item
              leftSection={<IconBarbell size={16} />}
              onClick={() => setShowTrainingModal(true)}
            >
              {t("train")}
            </Menu.Item>
          )}
          <Menu.Item
            leftSection={<IconShare size={16} />}
            onClick={() => setShowShareModal(true)}
          >
            {t("share")}
          </Menu.Item>
          <Menu.Divider />
          <Menu.Label>
            {conversation.number_of_messages} {t("messages")}
          </Menu.Label>
          <Menu.Label>
            {new Date(conversation.created_at).toLocaleString()}
          </Menu.Label>
        </Menu.Dropdown>
      </Menu>
    </div>
  ) : null;
};

// ─── ShareConversationModal ───────────────────────────────────────────────────

const ShareConversationModal = ({
  opened,
  onClose,
  conversationId,
}: {
  opened: boolean;
  onClose: () => void;
  conversationId: string;
}) => {
  const [validUntil, setValidUntil] = useState<Date | null>(null);
  const { t } = useTranslation();
  const [sharedId, setSharedId] = useState("");

  const share = async () => {
    const tid = toast.loading(t("sharing-conversation"));
    try {
      const res = await shareConversation(conversationId, validUntil);
      toast.dismiss(tid);
      setSharedId(res.id);
    } catch (e) {
      console.error("Failed to share conversation", e);
      toast.dismiss(tid);
      toast.error(t("failed-to-share-conversation"));
    }
  };

  const formatDateToLocalString = (date: Date) => {
    return date.toISOString().slice(0, 16);
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    toast.success(t("copied-to-clipboard"));
  };

  const generateShareLink = () => {
    return `${window.location.origin}/s?id=${sharedId}`;
  };

  const openLink = () => {
    window.open(generateShareLink(), "_blank");
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      onExitTransitionEnd={() => setSharedId("")}
      title={t("share-conversation")}
      centered
    >
      <Stack gap="md">
        {!sharedId ? (
          <>
            <Text>{t("share-conversation-description")}</Text>
            <TextInput
              type="datetime-local"
              defaultValue={
                validUntil ? formatDateToLocalString(validUntil) : ""
              }
              onChange={(e) => setValidUntil(new Date(e.currentTarget.value))}
            />
            <Button
              leftSection={<IconShare size={18} />}
              onClick={share}
              fullWidth
            >
              {t("share-now")}
            </Button>
          </>
        ) : (
          <>
            <Text
              ta="center"
              p="md"
              className="bg-green-500/20 rounded-lg"
            >
              {t("conversation-shared-message")}
            </Text>
            <div className="qr-display">
              <QRCodeDisplay size={256} url={generateShareLink()} />
            </div>
            <TextInput
              value={generateShareLink()}
              readOnly
              variant="filled"
            />
            <Group gap="xs" grow>
              <Button
                variant="default"
                leftSection={<IconCopy size={18} />}
                onClick={() => copyToClipboard(generateShareLink())}
              >
                {t("copy")}
              </Button>
              <Button
                variant="default"
                leftSection={<IconExternalLink size={18} />}
                onClick={openLink}
              >
                {t("open-link")}
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Modal>
  );
};

// ─── TrainingOnConversation ───────────────────────────────────────────────────

const TrainingOnConversation = ({
  opened,
  onClose,
  conversation,
}: {
  opened: boolean;
  onClose: () => void;
  conversation: TConversation;
}) => {
  const { t } = useTranslation();
  const { agents } = useStore((state) => ({
    agents: state.agents,
  }));

  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [completionsTargetNumber, setCompletionsTargetNumber] = useState(30);

  const toggleAgent = (slug: string) => {
    if (selectedAgents.includes(slug)) {
      setSelectedAgents((prev) => prev.filter((s) => s !== slug));
    } else {
      setSelectedAgents((prev) => [...prev, slug]);
    }
  };

  const generateTrainingData = async () => {
    if (selectedAgents.length === 0) {
      toast.error(t("please-select-at-least-one-agent"));
      return;
    }

    await generateTrainingCompletions({
      model_id: conversation.id,
      db_model: "conversation",
      agents: selectedAgents,
      completions_target_number: completionsTargetNumber,
    });
    toast.success(t("training-generation-in-queue"));
    onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      onExitTransitionEnd={() => {
        setSelectedAgents([]);
        setCompletionsTargetNumber(30);
      }}
      title={t("generate-completions")}
      centered
    >
      <Stack gap="md">
        <Text>
          {t("generate-completions-description")}{" "}
          <strong>{conversation.title}</strong>{" "}
          {t("generate-completions-description-2")}
        </Text>
        <Text>{t("after-generating-completions")}</Text>
        <NumberInput
          label={t("number-of-completions-to-generate")}
          value={completionsTargetNumber}
          onChange={(val) =>
            setCompletionsTargetNumber(typeof val === "number" ? val : 30)
          }
          min={1}
          variant="filled"
        />
        <Text size="sm">{t("select-agents-that-will-retrain")}</Text>
        <Group gap="xs" wrap="wrap">
          {agents.map((a) => (
            <Badge
              key={a.id}
              variant={
                selectedAgents.includes(a.slug) ? "filled" : "default"
              }
              style={{ cursor: "pointer" }}
              onClick={() => toggleAgent(a.slug)}
            >
              {a.name}
            </Badge>
          ))}
        </Group>
        <Button
          leftSection={<IconBarbell size={18} />}
          onClick={generateTrainingData}
          fullWidth
        >
          Generate
        </Button>
      </Stack>
    </Modal>
  );
};
