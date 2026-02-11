import React, { useState, useMemo, useEffect } from "react";
import { TConversation, TTag, TConversationAlertRule } from "../../types";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { getTags, getAlertRules } from "../../modules/apiCalls";
import {
  ActionIcon,
  Badge,
  Button,
  Card,
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
} from "@mantine/core";
import { DateInput } from "@mantine/dates";
import {
  IconAlertTriangle,
  IconChevronDown,
  IconChevronRight,
  IconFilterOff,
} from "@tabler/icons-react";

interface ConversationsTableProps {
  conversations: TConversation[];
}

export const ConversationsTable: React.FC<ConversationsTableProps> = ({
  conversations,
}) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [tags, setTags] = useState<TTag[]>([]);
  const [alertRules, setAlertRules] = useState<TConversationAlertRule[]>([]);

  useEffect(() => {
    getTags()
      .then((data) => setTags(data))
      .catch((err) => console.error("Error loading tags:", err));
    getAlertRules()
      .then((data) => setAlertRules(data))
      .catch((err) => console.error("Error loading alert rules:", err));
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

    filtered.sort((a, b) => {
      const dateA = new Date(a.created_at).getTime();
      const dateB = new Date(b.created_at).getTime();
      return filters.sortBy === "newest" ? dateB - dateA : dateA - dateB;
    });

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

  return (
    <Stack gap="md">
      {/* Filters */}
      <Card withBorder padding="md" radius="md">
        <Title order={5} mb="sm">
          {t("filters")}
        </Title>
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

          <Table.ScrollContainer minWidth={500}>
            <Table highlightOnHover>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th w={40} />
                  <Table.Th>{t("title")}</Table.Th>
                  <Table.Th>{t("user")}</Table.Th>
                  <Table.Th>{t("messages")}</Table.Th>
                  <Table.Th>{t("date")}</Table.Th>
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
                          <Text size="sm">
                          {conv.user_username ??
                            (conv.user_id != null
                              ? String(conv.user_id)
                              : "-")}
                        </Text>
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
                          <Table.Td colSpan={7} py="sm" px="md">
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
