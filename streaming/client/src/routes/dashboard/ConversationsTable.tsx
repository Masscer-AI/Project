import React, { useState, useMemo, useEffect } from "react";
import {
  TConversation,
  TTag,
  TConversationAlertRule,
  TChatWidget,
} from "../../types";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import {
  bulkConversationAction,
  getTags,
  getAlertRules,
  getChatWidgets,
} from "../../modules/apiCalls";
import { useStore } from "../../modules/store";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Checkbox,
  Group,
  MultiSelect,
  NativeSelect,
  NumberInput,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  UnstyledButton,
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import {
  IconAlertTriangle,
  IconDeviceDesktop,
  IconChevronDown,
  IconChevronRight,
  IconFilter,
  IconFilterOff,
  IconUsers,
} from "@tabler/icons-react";

interface ConversationsTableProps {
  conversations: TConversation[];
  onConversationsChanged?: () => Promise<void> | void;
}

export const ConversationsTable: React.FC<ConversationsTableProps> = ({
  conversations,
  onConversationsChanged,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const currentUserId = useStore((state) => state.user?.id);
  const [tags, setTags] = useState<TTag[]>([]);
  const [alertRules, setAlertRules] = useState<TConversationAlertRule[]>([]);
  const [chatWidgets, setChatWidgets] = useState<TChatWidget[]>([]);

  useEffect(() => {
    getTags()
      .then((data) => setTags(data))
      .catch((err) => console.error("Error loading tags:", err));
    getAlertRules()
      .then((data) => setAlertRules(data))
      .catch((err) => console.error("Error loading alert rules:", err));
    getChatWidgets()
      .then((data) => setChatWidgets(data))
      .catch((err) => console.error("Error loading chat widgets:", err));
  }, []);

  const tagMap = useMemo(() => {
    const map = new Map<number, { name: string; color: string }>();
    tags.forEach((tag) => {
      map.set(tag.id, {
        name: tag.title,
        color: tag.color || "#4a9eff",
      });
    });
    return map;
  }, [tags]);

  const safeConversations = Array.isArray(conversations) ? conversations : [];
  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());
  const [selectedConversationIds, setSelectedConversationIds] = useState<Set<string>>(
    new Set()
  );
  const [showFilters, setShowFilters] = useState(false);

  const toggleRow = (id: string) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const [filters, setFilters] = useState({
    search: "",
    userId: "",
    sortBy: "newest" as "newest" | "oldest",
    dateFrom: null as Date | null,
    dateTo: null as Date | null,
    minMessages: "" as number | string,
    maxMessages: "" as number | string,
    selectedTags: [] as number[],
    selectedAlertRules: [] as string[],
    chatWidgetId: "",
    status: "active_inactive" as
      | "active_inactive"
      | "all"
      | "active"
      | "inactive"
      | "archived"
      | "deleted",
    messagesSort: "none" as "none" | "asc" | "desc",
  });

  const { uniqueUserIds, userDisplayMap } = useMemo(() => {
    const ids = new Set<number>();
    const displayMap = new Map<number, string>();
    safeConversations.forEach((conv) => {
      if (conv?.user_id != null) {
        ids.add(conv.user_id);
        if (conv.user_username)
          displayMap.set(conv.user_id, conv.user_username);
      }
    });
    return {
      uniqueUserIds: Array.from(ids).sort((a, b) => a - b),
      userDisplayMap: displayMap,
    };
  }, [safeConversations]);

  const filteredConversations = useMemo(() => {
    let filtered = [...safeConversations];

    // Hide empty conversations: no title AND 0 messages
    filtered = filtered.filter(
      (conv) =>
        (conv.title && conv.title.trim()) || (conv.number_of_messages ?? 0) > 0
    );

    if (filters.search) {
      const searchLower = filters.search.toLowerCase();
      filtered = filtered.filter((conv) => {
        const titleMatch = conv.title?.toLowerCase().includes(searchLower);
        const idMatch = conv.id.toLowerCase().includes(searchLower);
        const tagsMatch = conv.tags?.some((tagId) => {
          const tagInfo = tagMap.get(tagId);
          return tagInfo?.name.toLowerCase().includes(searchLower) || false;
        });
        const summaryMatch = conv.summary?.toLowerCase().includes(searchLower);
        return titleMatch || idMatch || tagsMatch || summaryMatch;
      });
    }

    if (filters.userId) {
      filtered = filtered.filter(
        (conv) => conv.user_id != null && String(conv.user_id) === filters.userId
      );
    }

    if (filters.dateFrom) {
      const fromDate = filters.dateFrom;
      filtered = filtered.filter(
        (conv) => new Date(conv.created_at) >= fromDate
      );
    }
    if (filters.dateTo) {
      const toDate = new Date(filters.dateTo);
      toDate.setHours(23, 59, 59, 999);
      filtered = filtered.filter(
        (conv) => new Date(conv.created_at) <= toDate
      );
    }

    if (typeof filters.minMessages === "number") {
      const min = filters.minMessages;
      filtered = filtered.filter(
        (conv) => (conv.number_of_messages || 0) >= min
      );
    }
    if (typeof filters.maxMessages === "number") {
      const max = filters.maxMessages;
      filtered = filtered.filter(
        (conv) => (conv.number_of_messages || 0) <= max
      );
    }

    if (filters.selectedTags.length > 0) {
      filtered = filtered.filter((conv) =>
        conv.tags?.some((tagId) => filters.selectedTags.includes(tagId))
      );
    }

    if (filters.selectedAlertRules.length > 0) {
      filtered = filtered.filter((conv) =>
        conv.alert_rule_ids?.some((ruleId) =>
          filters.selectedAlertRules.includes(ruleId)
        )
      );
    }

    if (filters.chatWidgetId) {
      if (filters.chatWidgetId === "none") {
        filtered = filtered.filter((conv) => conv.chat_widget_id == null);
      } else {
        filtered = filtered.filter(
          (conv) => String(conv.chat_widget_id ?? "") === filters.chatWidgetId
        );
      }
    }

    if (filters.status !== "all") {
      if (filters.status === "active_inactive") {
        filtered = filtered.filter(
          (conv) => conv.status === "active" || conv.status === "inactive"
        );
      } else {
        filtered = filtered.filter((conv) => conv.status === filters.status);
      }
    }

    if (filters.messagesSort !== "none") {
      filtered.sort((a, b) => {
        const aCount = a.number_of_messages || 0;
        const bCount = b.number_of_messages || 0;
        if (filters.messagesSort === "asc") return aCount - bCount;
        return bCount - aCount;
      });
    } else {
      filtered.sort((a, b) => {
        const dateA = new Date(a.created_at).getTime();
        const dateB = new Date(b.created_at).getTime();
        return filters.sortBy === "newest" ? dateB - dateA : dateA - dateB;
      });
    }

    return filtered;
  }, [safeConversations, filters, tagMap]);

  const clearFilters = () => {
    setFilters({
      search: "",
      userId: "",
      sortBy: "newest",
      dateFrom: null,
      dateTo: null,
      minMessages: "",
      maxMessages: "",
      selectedTags: [],
      selectedAlertRules: [],
      chatWidgetId: "",
      status: "active_inactive",
      messagesSort: "none",
    });
  };

  const userOptions = [
    { value: "", label: t("all-users") },
    ...uniqueUserIds.map((userId) => ({
      value: userId.toString(),
      label: userDisplayMap.get(userId) ?? `${t("user")} ${userId}`,
    })),
  ];

  const sortOptions = [
    { value: "newest", label: t("newest-first") },
    { value: "oldest", label: t("oldest-first") },
  ];

  const chatWidgetMap = useMemo(() => {
    const map = new Map<number, string>();
    chatWidgets.forEach((widget) => {
      map.set(widget.id, widget.name || `Widget ${widget.id}`);
    });
    return map;
  }, [chatWidgets]);

  const chatWidgetOptions = [
    { value: "", label: "All widgets" },
    { value: "none", label: "No widget" },
    ...chatWidgets.map((widget) => ({
      value: String(widget.id),
      label: widget.name || `Widget ${widget.id}`,
    })),
  ];

  const toggleMessagesSort = () => {
    setFilters((prev) => ({
      ...prev,
      messagesSort:
        prev.messagesSort === "none"
          ? "desc"
          : prev.messagesSort === "desc"
            ? "asc"
            : "none",
    }));
  };

  const statusOptions = [
    { value: "active_inactive", label: "Active + Inactive" },
    { value: "all", label: "All statuses" },
    { value: "active", label: "Active" },
    { value: "inactive", label: "Inactive" },
    { value: "archived", label: "Archived" },
    { value: "deleted", label: "Deleted" },
  ];

  const allFilteredIds = filteredConversations.map((c) => c.id);
  const allFilteredSelected =
    allFilteredIds.length > 0 &&
    allFilteredIds.every((id) => selectedConversationIds.has(id));
  const someFilteredSelected =
    allFilteredIds.some((id) => selectedConversationIds.has(id)) &&
    !allFilteredSelected;

  const toggleSelectAllFiltered = () => {
    setSelectedConversationIds((prev) => {
      const next = new Set(prev);
      if (allFilteredSelected) {
        allFilteredIds.forEach((id) => next.delete(id));
      } else {
        allFilteredIds.forEach((id) => next.add(id));
      }
      return next;
    });
  };

  const toggleSelectConversation = (conversationId: string) => {
    setSelectedConversationIds((prev) => {
      const next = new Set(prev);
      if (next.has(conversationId)) next.delete(conversationId);
      else next.add(conversationId);
      return next;
    });
  };

  const runBulkAction = async (action: "archive" | "unarchive" | "delete") => {
    const ids = Array.from(selectedConversationIds);
    if (ids.length === 0) return;
    try {
      await bulkConversationAction(action, ids);
      setSelectedConversationIds(new Set());
      if (onConversationsChanged) await onConversationsChanged();
    } catch (error) {
      console.error(`Error running bulk ${action}:`, error);
    }
  };

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Title order={5}>{t("filters")}</Title>
        <Button
          variant={showFilters ? "default" : "subtle"}
          color="gray"
          size="sm"
          leftSection={<IconFilter size={16} />}
          onClick={() => setShowFilters((prev) => !prev)}
        >
          {showFilters ? "Ocultar filtros" : "Mostrar filtros"}
        </Button>
      </Group>

      {/* Filters */}
      {showFilters && (
        <Card withBorder padding="md" radius="md">
          <SimpleGrid cols={{ base: 2, md: 3, lg: 4 }} spacing="sm">
            <TextInput
              label={t("search-by-keywords")}
              placeholder={t("search-by-keywords")}
              size="sm"
              value={filters.search}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setFilters((prev) => ({ ...prev, search: val }));
              }}
            />

            <NativeSelect
              label={t("user")}
              size="sm"
              data={userOptions}
              value={filters.userId}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setFilters((prev) => ({ ...prev, userId: val }));
              }}
            />

            <DateInput
              label={t("date-from")}
              size="sm"
              clearable
              value={filters.dateFrom}
              onChange={(val) => {
                const date = val ? new Date(val) : null;
                setFilters((prev) => ({ ...prev, dateFrom: date }));
              }}
            />

            <DateInput
              label={t("date-to")}
              size="sm"
              clearable
              value={filters.dateTo}
              onChange={(val) => {
                const date = val ? new Date(val) : null;
                setFilters((prev) => ({ ...prev, dateTo: date }));
              }}
            />

            <NumberInput
              label={t("min-messages")}
              size="sm"
              placeholder="0"
              min={0}
              value={filters.minMessages}
              onChange={(val) =>
                setFilters((prev) => ({ ...prev, minMessages: val }))
              }
            />

            <NumberInput
              label={t("max-messages")}
              size="sm"
              placeholder="∞"
              min={0}
              value={filters.maxMessages}
              onChange={(val) =>
                setFilters((prev) => ({ ...prev, maxMessages: val }))
              }
            />

            <MultiSelect
              label={t("tags")}
              size="sm"
              placeholder={t("all")}
              clearable
              searchable
              data={tags
                .filter((tag) => tag.enabled)
                .map((tag) => ({
                  value: tag.id.toString(),
                  label: tag.title,
                }))}
              value={filters.selectedTags.map(String)}
              onChange={(vals) =>
                setFilters((prev) => ({
                  ...prev,
                  selectedTags: vals.map(Number),
                }))
              }
            />

            <MultiSelect
              label={t("alerts")}
              size="sm"
              placeholder={t("all")}
              clearable
              searchable
              data={alertRules
                .filter((rule) => rule.enabled)
                .map((rule) => ({
                  value: rule.id,
                  label: rule.name,
                }))}
              value={filters.selectedAlertRules}
              onChange={(vals) =>
                setFilters((prev) => ({
                  ...prev,
                  selectedAlertRules: vals,
                }))
              }
            />

            <NativeSelect
              label={t("sort-by")}
              size="sm"
              data={sortOptions}
              value={filters.sortBy}
              onChange={(e) => {
                const val = e.currentTarget.value as "newest" | "oldest";
                setFilters((prev) => ({ ...prev, sortBy: val }));
              }}
            />

            <NativeSelect
              label="Chat widget"
              size="sm"
              data={chatWidgetOptions}
              value={filters.chatWidgetId}
              onChange={(e) => {
                const val = e.currentTarget.value;
                setFilters((prev) => ({ ...prev, chatWidgetId: val }));
              }}
            />

            <NativeSelect
              label="Status"
              size="sm"
              data={statusOptions}
              value={filters.status}
              onChange={(e) => {
                const val = e.currentTarget.value as typeof filters.status;
                setFilters((prev) => ({ ...prev, status: val }));
              }}
            />

            <Button
              variant="subtle"
              color="gray"
              size="sm"
              leftSection={<IconFilterOff size={16} />}
              onClick={clearFilters}
              style={{ alignSelf: "flex-end" }}
            >
              {t("clear-filters")}
            </Button>
          </SimpleGrid>
        </Card>
      )}

      {/* Table */}
      {filteredConversations.length === 0 ? (
        <Text ta="center" c="dimmed" py="xl">
          {t("no-conversations")}
        </Text>
      ) : (
        <>
          <Text size="sm" c="dimmed">
            {t("showing")} {filteredConversations.length} {t("of")}{" "}
            {safeConversations.length} {t("conversations")}
          </Text>

          {selectedConversationIds.size > 0 && (
            <Group justify="space-between">
              <Text size="sm" c="dimmed">
                {selectedConversationIds.size} selected
              </Text>
              <Group gap="xs">
                <Button
                  size="xs"
                  variant="default"
                  onClick={() => runBulkAction("archive")}
                >
                  Archive
                </Button>
                {(filters.status === "all" || filters.status === "archived") && (
                  <Button
                    size="xs"
                    variant="default"
                    onClick={() => runBulkAction("unarchive")}
                  >
                    Unarchive
                  </Button>
                )}
                <Button
                  size="xs"
                  color="red"
                  variant="light"
                  onClick={() => runBulkAction("delete")}
                >
                  Delete
                </Button>
              </Group>
            </Group>
          )}

          <Table.ScrollContainer minWidth={500}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th
                    w={40}
                    onClick={(e) => {
                      e.stopPropagation();
                    }}
                  >
                    <Checkbox
                      checked={allFilteredSelected}
                      indeterminate={someFilteredSelected}
                      onChange={toggleSelectAllFiltered}
                      onClick={(e) => {
                        e.stopPropagation();
                      }}
                    />
                  </Table.Th>
                  <Table.Th w={40} />
                  <Table.Th>{t("title")}</Table.Th>
                  <Table.Th>Identity</Table.Th>
                  <Table.Th>
                    <UnstyledButton onClick={toggleMessagesSort}>
                      <Group gap={4} wrap="nowrap">
                        <Text size="sm" fw={600}>
                          {t("messages")}
                        </Text>
                        {filters.messagesSort === "desc" ? (
                          <IconChevronDown size={14} />
                        ) : filters.messagesSort === "asc" ? (
                          <IconChevronRight
                            size={14}
                            style={{ transform: "rotate(-90deg)" }}
                          />
                        ) : null}
                      </Group>
                    </UnstyledButton>
                  </Table.Th>
                  <Table.Th>{t("date")}</Table.Th>
                  <Table.Th>Status</Table.Th>
                  <Table.Th>{t("tags")}</Table.Th>
                  <Table.Th>{t("alerts")}</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {filteredConversations.map((conv) => {
                  const isExpanded = expandedRows.has(conv.id);
                  return (
                    <React.Fragment key={conv.id}>
                      <Table.Tr
                        onClick={() => navigate(`/chat?conversation=${conv.id}`)}
                        style={{ cursor: "pointer" }}
                      >
                        <Table.Td
                          onClick={(e) => {
                            e.stopPropagation();
                          }}
                        >
                          <Checkbox
                            checked={selectedConversationIds.has(conv.id)}
                            onChange={(e) => {
                              e.stopPropagation();
                              toggleSelectConversation(conv.id);
                            }}
                            onClick={(e) => {
                              e.stopPropagation();
                            }}
                          />
                        </Table.Td>
                        <Table.Td>
                          <ActionIcon
                            variant="subtle"
                            color="gray"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              toggleRow(conv.id);
                            }}
                          >
                            {isExpanded ? (
                              <IconChevronDown size={16} />
                            ) : (
                              <IconChevronRight size={16} />
                            )}
                          </ActionIcon>
                        </Table.Td>
                        <Table.Td maw={250}>
                          <Text size="sm" truncate>
                            {conv.title || conv.id.slice(0, 20) + "..."}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          {conv.chat_widget_id != null ? (
                            <Badge
                              size="sm"
                              variant="light"
                              color="violet"
                              leftSection={<IconDeviceDesktop size={12} />}
                            >
                              {chatWidgetMap.get(conv.chat_widget_id) ??
                                `Widget ${conv.chat_widget_id}`}
                            </Badge>
                          ) : conv.user_username || conv.user_id != null ? (
                            <Badge
                              size="sm"
                              variant="light"
                              color="blue"
                              leftSection={<IconUsers size={12} />}
                            >
                              {conv.user_id != null && currentUserId != null && conv.user_id === currentUserId
                                ? t("you")
                                : conv.user_username ??
                                  (conv.user_id != null ? String(conv.user_id) : "-")}
                            </Badge>
                          ) : (
                            <Text size="sm" c="dimmed">
                              -
                            </Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">
                            {conv.number_of_messages || 0}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Text size="sm">
                            {conv.created_at
                              ? new Date(
                                  conv.created_at
                                ).toLocaleDateString()
                              : "-"}
                          </Text>
                        </Table.Td>
                        <Table.Td>
                          <Badge
                            size="sm"
                            variant="light"
                            color={
                              conv.status === "active"
                                ? "green"
                                : conv.status === "inactive"
                                  ? "gray"
                                  : conv.status === "archived"
                                    ? "yellow"
                                    : conv.status === "deleted"
                                      ? "red"
                                      : "gray"
                            }
                          >
                            {conv.status || "unknown"}
                          </Badge>
                        </Table.Td>
                        <Table.Td>
                          {conv.tags && conv.tags.length > 0 ? (
                            <Group gap={4} wrap="wrap">
                              {conv.tags.slice(0, 3).map((tagId, idx) => {
                                const tagInfo = tagMap.get(tagId);
                                if (!tagInfo) return null;
                                return (
                                  <Badge
                                    key={idx}
                                    size="xs"
                                    color={tagInfo.color}
                                    variant="filled"
                                  >
                                    {tagInfo.name}
                                  </Badge>
                                );
                              })}
                              {conv.tags.length > 3 && (
                                <Text size="xs" c="dimmed">
                                  +{conv.tags.length - 3}
                                </Text>
                              )}
                            </Group>
                          ) : (
                            <Text size="sm" c="dimmed">
                              -
                            </Text>
                          )}
                        </Table.Td>
                        <Table.Td>
                          {(conv.alerts_count || 0) > 0 ? (
                            <Group gap={4} wrap="nowrap">
                              <IconAlertTriangle size={14} />
                              <Text size="sm">{conv.alerts_count}</Text>
                            </Group>
                          ) : (
                            <Text size="sm" c="dimmed">
                              -
                            </Text>
                          )}
                        </Table.Td>
                      </Table.Tr>
                      {isExpanded && (
                        <Table.Tr>
                          <Table.Td colSpan={9} py="sm" px="md">
                            <Text size="sm" fw={500} mb={4}>
                              {t("summary")}
                            </Text>
                            <Text size="sm" c="dimmed">
                              {conv.summary || t("no-summary-available")}
                            </Text>
                          </Table.Td>
                        </Table.Tr>
                      )}
                    </React.Fragment>
                  );
                })}
              </Table.Tbody>
            </Table>
          </Table.ScrollContainer>
        </>
      )}
    </Stack>
  );
};
