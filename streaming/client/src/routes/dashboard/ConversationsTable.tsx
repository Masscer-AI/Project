import React, { useState, useMemo, useEffect, useCallback } from "react";
import {
  TConversation,
  TTag,
  TConversationAlertRule,
  TChatWidget,
} from "../../types";
import type { TConversationFilters } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { useNavigate, Link } from "react-router-dom";
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
  Loader,
  MultiSelect,
  NativeSelect,
  NumberInput,
  Pagination,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
  Tooltip,
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

/** Parse date from picker (string or Date) as local noon to avoid timezone display bugs. */
function parseDateForPicker(val: string | Date): Date {
  if (typeof val === "string" && /^\d{4}-\d{2}-\d{2}/.test(val)) {
    const [y, m, d] = val.slice(0, 10).split("-").map(Number);
    return new Date(y, m - 1, d, 12, 0, 0);
  }
  const d = new Date(val);
  return new Date(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate(), 12, 0, 0);
}

interface ConversationsTableProps {
  conversations: TConversation[];
  total: number;
  page: number;
  pageSize: number;
  filters: TConversationFilters;
  filterOptions?: { users: { id: number; label: string }[] };
  onFiltersChange: (filters: TConversationFilters) => void;
  onPageChange: (page: number) => void;
  onConversationsChanged?: () => Promise<void> | void;
  isLoading?: boolean;
}

export const ConversationsTable: React.FC<ConversationsTableProps> = ({
  conversations,
  total,
  page,
  pageSize,
  filters,
  filterOptions,
  onFiltersChange,
  onPageChange,
  onConversationsChanged,
  isLoading = false,
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
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const updateFilters = useCallback(
    (updates: Partial<TConversationFilters>) => {
      onFiltersChange({ ...filters, ...updates });
    },
    [filters, onFiltersChange]
  );

  const clearFilters = useCallback(() => {
    onFiltersChange({
      scope: filters.scope ?? "org",
      search: "",
      userId: "",
      sortBy: "newest",
      dateFrom: null,
      dateTo: null,
      minMessages: 1,
      maxMessages: "" as unknown as number,
      selectedTags: [],
      selectedAlertRules: [],
      chatWidgetId: "",
      status: "all",
      messagesSort: "none",
    });
  }, [filters.scope, onFiltersChange]);

  const userOptions = [
    { value: "", label: t("all-users") },
    ...(filterOptions?.users ?? []).map((u) => ({
      value: String(u.id),
      label: u.label,
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
    const next =
      filters.messagesSort === "none"
        ? "desc"
        : filters.messagesSort === "desc"
          ? "asc"
          : "none";
    updateFilters({ messagesSort: next });
  };

  const statusOptions = [
    { value: "active_inactive", label: "Active + Inactive" },
    { value: "all", label: "All statuses" },
    { value: "active", label: "Active" },
    { value: "inactive", label: "Inactive" },
    { value: "archived", label: "Archived" },
    { value: "deleted", label: "Deleted" },
  ];

  const allFilteredIds = safeConversations.map((c) => c.id);
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
              value={filters.search ?? ""}
              onChange={(e) => {
                const val = e.currentTarget.value;
                updateFilters({ search: val });
              }}
            />

            <NativeSelect
              label={t("user")}
              size="sm"
              data={userOptions}
              value={filters.userId ?? ""}
              onChange={(e) => {
                const val = e.currentTarget.value;
                updateFilters({ userId: val });
              }}
            />

            <DateInput
              label={t("date-from")}
              size="sm"
              clearable
              value={filters.dateFrom ?? null}
              onChange={(val) => {
                if (!val) {
                  updateFilters({ dateFrom: null });
                  return;
                }
                const date = parseDateForPicker(val);
                updateFilters({ dateFrom: date });
              }}
            />

            <DateInput
              label={t("date-to")}
              size="sm"
              clearable
              value={filters.dateTo ?? null}
              onChange={(val) => {
                if (!val) {
                  updateFilters({ dateTo: null });
                  return;
                }
                const date = parseDateForPicker(val);
                updateFilters({ dateTo: date });
              }}
            />

            <NumberInput
              label={t("min-messages")}
              size="sm"
              placeholder="1"
              min={1}
              value={filters.minMessages ?? ""}
              onChange={(val) => updateFilters({ minMessages: val as number })}
            />

            <NumberInput
              label={t("max-messages")}
              size="sm"
              placeholder="∞"
              min={0}
              value={filters.maxMessages ?? ""}
              onChange={(val) => updateFilters({ maxMessages: val as number })}
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
              value={(filters.selectedTags ?? []).map(String)}
              onChange={(vals) =>
                updateFilters({ selectedTags: vals.map(Number) })
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
              value={filters.selectedAlertRules ?? []}
              onChange={(vals) =>
                updateFilters({ selectedAlertRules: vals })
              }
            />

            <NativeSelect
              label={t("sort-by")}
              size="sm"
              data={sortOptions}
              value={filters.sortBy ?? "newest"}
              onChange={(e) => {
                const val = e.currentTarget.value as "newest" | "oldest";
                updateFilters({ sortBy: val });
              }}
            />

            <NativeSelect
              label="Chat widget"
              size="sm"
              data={chatWidgetOptions}
              value={filters.chatWidgetId ?? ""}
              onChange={(e) => {
                const val = e.currentTarget.value;
                updateFilters({ chatWidgetId: val });
              }}
            />

            <NativeSelect
              label="Status"
              size="sm"
              data={statusOptions}
              value={filters.status ?? "all"}
              onChange={(e) => {
                const val = e.currentTarget.value as typeof filters.status;
                updateFilters({ status: val });
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
      {isLoading ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : safeConversations.length === 0 ? (
        <Text ta="center" c="dimmed" py="xl">
          {t("no-conversations")}
        </Text>
      ) : (
        <>
          <Group justify="space-between" wrap="nowrap">
            <Text size="sm" c="dimmed">
              {t("showing")}{" "}
              {total === 0
                ? 0
                : `${page * pageSize + 1}-${Math.min(page * pageSize + pageSize, total)}`}{" "}
              {t("of")} {total} {t("conversations")}
            </Text>
            {total > pageSize && (
              <Pagination
                total={Math.ceil(total / pageSize)}
                value={page + 1}
                onChange={(p) => onPageChange(p - 1)}
                size="sm"
              />
            )}
          </Group>

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
                {safeConversations.map((conv) => {
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
                        <Table.Td
                          onClick={(e) => e.stopPropagation()}
                        >
                          {(conv.alerts_count || 0) > 0 ? (
                            <Tooltip label={t("open-alerts")} withArrow>
                              <UnstyledButton
                                component={Link}
                                to={`/dashboard/alerts?conversation=${conv.id}`}
                                style={{ display: "inline-flex" }}
                              >
                                <Group gap={4} wrap="nowrap" style={{ cursor: "pointer" }}>
                                  <IconAlertTriangle
                                    size={14}
                                    color={conv.has_pending_alerts ? "var(--mantine-color-red-6)" : undefined}
                                  />
                                  <Text
                                    size="sm"
                                    c={conv.has_pending_alerts ? "red" : undefined}
                                  >
                                    {conv.alerts_count}
                                  </Text>
                                </Group>
                              </UnstyledButton>
                            </Tooltip>
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
