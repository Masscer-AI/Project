import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Button,
  Group,
  Loader,
  Modal,
  Select,
  Stack,
  Text,
  TextInput,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconCalendar, IconChevronDown, IconChevronRight, IconFilter, IconMessage, IconRobot, IconSearch, IconStack2 } from "@tabler/icons-react";
import { AppPage } from "../../components/AppPage/AppPage";
import { getAgents, getAllConversations, getTags } from "../../modules/apiCalls";
import { TConversation, TTag } from "../../types";
import { TAgent } from "../../types/agents";

type DatePreset = "any" | "today" | "week" | "month";
type GroupBy = "date" | "tag" | "agent";

type ConversationGroup = {
  key: string;
  label: string;
  tag?: TTag;
  items: TConversation[];
};

function tagDotColor(color?: string) {
  if (!color) return "var(--mantine-color-violet-filled)";
  if (color.startsWith("#") || color.startsWith("rgb")) return color;
  return `var(--mantine-color-${color}-filled)`;
}

function dayKey(iso: string) {
  const d = new Date(iso);
  return `${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`;
}

function formatDay(iso: string, locale: string) {
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "long",
    year: "numeric",
  }).format(new Date(iso));
}

function formatTime(iso: string, locale: string) {
  return new Intl.DateTimeFormat(locale, {
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function startOfDay(date: Date) {
  const next = new Date(date);
  next.setHours(0, 0, 0, 0);
  return next;
}

function relatedAgentIds(conversation: TConversation) {
  return (conversation.metadata?.related_agents || []).map((agent) => agent.id);
}

function hasEnabledTag(conversation: TConversation, enabledIds: Set<number>) {
  return (conversation.tags || []).some((tagId) => enabledIds.has(tagId));
}

function tagInitial(title: string) {
  return title.trim().charAt(0).toLocaleUpperCase();
}

function TagMark({ tag }: { tag: TTag }) {
  return (
    <Tooltip label={tag.title} withArrow>
      <Box
        w={18}
        h={18}
        style={{
          borderRadius: 99,
          background: tagDotColor(tag.color),
          color: "#fff",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 10,
          fontWeight: 700,
          flexShrink: 0,
          lineHeight: 1,
        }}
      >
        {tagInitial(tag.title)}
      </Box>
    </Tooltip>
  );
}

function AgentChip({ name }: { name: string }) {
  return (
    <Group gap={6} wrap="nowrap">
      <IconRobot size={12} style={{ flexShrink: 0 }} />
      <Text size="xs" style={{ whiteSpace: "nowrap" }}>
        {name}
      </Text>
    </Group>
  );
}

function TagChip({ tag }: { tag: TTag }) {
  return (
    <Group gap={6} wrap="nowrap">
      <Box
        w={8}
        h={8}
        style={{
          borderRadius: 99,
          background: tagDotColor(tag.color),
          flexShrink: 0,
        }}
      />
      <Text size="xs" style={{ whiteSpace: "nowrap" }}>
        {tag.title}
      </Text>
    </Group>
  );
}

function DatePresetSelect({
  value,
  onChange,
  fullWidth,
  t,
}: {
  value: DatePreset;
  onChange: (value: DatePreset) => void;
  fullWidth: boolean;
  t: (key: string) => string;
}) {
  return (
    <Select
      value={value}
      onChange={(next) => {
        if (next === "any" || next === "today" || next === "week" || next === "month") {
          onChange(next);
        }
      }}
      data={[
        { value: "any", label: t("any-date") },
        { value: "today", label: t("today") },
        { value: "week", label: t("last-7-days") },
        { value: "month", label: t("last-30-days") },
      ]}
      leftSection={<IconCalendar size={16} />}
      allowDeselect={false}
      w={fullWidth ? "100%" : 200}
    />
  );
}

function GroupBySelect({
  value,
  onChange,
  fullWidth,
  t,
}: {
  value: GroupBy;
  onChange: (value: GroupBy) => void;
  fullWidth: boolean;
  t: (key: string) => string;
}) {
  return (
    <Select
      aria-label={t("group-by")}
      value={value}
      onChange={(next) => {
        if (next === "date" || next === "tag" || next === "agent") onChange(next);
      }}
      data={[
        { value: "date", label: t("by-date") },
        { value: "tag", label: t("by-tag") },
        { value: "agent", label: t("by-agent") },
      ]}
      leftSection={<IconStack2 size={16} />}
      allowDeselect={false}
      w={fullWidth ? "100%" : 200}
    />
  );
}

function ChipFilters({
  tags,
  agents,
  selectedTags,
  selectedAgents,
  onToggleTag,
  untagged,
  onToggleUntagged,
  onToggleAgent,
  t,
}: {
  tags: TTag[];
  agents: Array<TAgent & { id: number }>;
  selectedTags: number[];
  selectedAgents: number[];
  onToggleTag: (tagId: number) => void;
  untagged: boolean;
  onToggleUntagged: () => void;
  onToggleAgent: (agentId: number) => void;
  t: (key: string) => string;
}) {
  return (
    <>
      {tags.length > 0 && (
        <Stack gap={6}>
          <Text size="xs" c="dimmed" fw={600}>
            {t("tags")}
          </Text>
          <Group gap="xs" wrap="wrap">
            {tags.map((tag) => {
              const active = selectedTags.includes(tag.id);
              return (
                <UnstyledButton
                  key={tag.id}
                  onClick={() => onToggleTag(tag.id)}
                  px="sm"
                  py={6}
                  style={{
                    borderRadius: 999,
                    border: `1px solid ${
                      active ? tagDotColor(tag.color) : "var(--mantine-color-dark-4)"
                    }`,
                  }}
                >
                  <TagChip tag={tag} />
                </UnstyledButton>
              );
            })}
            <UnstyledButton
              onClick={onToggleUntagged}
              px="sm"
              py={6}
              style={{
                borderRadius: 999,
                border: `1px solid ${
                  untagged ? "var(--mantine-color-gray-5)" : "var(--mantine-color-dark-4)"
                }`,
              }}
            >
              <Text size="xs" style={{ whiteSpace: "nowrap" }}>
                {t("no-tag")}
              </Text>
            </UnstyledButton>
          </Group>
        </Stack>
      )}
      {agents.length > 0 && (
        <Stack gap={6}>
          <Text size="xs" c="dimmed" fw={600}>
            {t("agents")}
          </Text>
          <Group gap="xs" wrap="wrap">
            {agents.map((agent) => {
              const active = selectedAgents.includes(agent.id);
              return (
                <UnstyledButton
                  key={agent.id}
                  onClick={() => onToggleAgent(agent.id)}
                  px="sm"
                  py={6}
                  style={{
                    borderRadius: 999,
                    border: `1px solid ${
                      active
                        ? "var(--mantine-color-violet-filled)"
                        : "var(--mantine-color-dark-4)"
                    }`,
                  }}
                >
                  <AgentChip name={agent.name} />
                </UnstyledButton>
              );
            })}
          </Group>
        </Stack>
      )}
    </>
  );
}

export default function ConversationsPage() {
  const { t, i18n } = useTranslation();
  const [history, setHistory] = useState<TConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [orgTags, setOrgTags] = useState<TTag[]>([]);
  const [agents, setAgents] = useState<TAgent[]>([]);
  const [title, setTitle] = useState("");
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [untagged, setUntagged] = useState(false);
  const [selectedAgents, setSelectedAgents] = useState<number[]>([]);
  const [datePreset, setDatePreset] = useState<DatePreset>("any");
  const [groupBy, setGroupBy] = useState<GroupBy>("date");
  const [filtersOpened, { open: openFilters, close: closeFilters }] = useDisclosure(false);
  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());

  const load = () => {
    getAllConversations("personal")
      .then((res) => setHistory(res))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
    getTags()
      .then((tags) => setOrgTags(tags))
      .catch(() => setOrgTags([]));
    getAgents()
      .then((res) => setAgents(res?.agents ?? []))
      .catch(() => setAgents([]));
  }, []);

  useEffect(() => {
    const refresh = () => load();
    window.addEventListener("conversations-changed", refresh);
    return () => window.removeEventListener("conversations-changed", refresh);
  }, []);

  const tagById = useMemo(() => {
    const map = new Map<number, TTag>();
    orgTags.forEach((tag) => map.set(tag.id, tag));
    return map;
  }, [orgTags]);

  const namedAgents = useMemo(
    () =>
      agents
        .filter((agent): agent is TAgent & { id: number } => agent.id != null)
        .slice()
        .sort((a, b) => a.name.localeCompare(b.name, i18n.language)),
    [agents, i18n.language]
  );

  const enabledTags = orgTags.filter((tag) => tag.enabled);

  const filteredHistory = useMemo(() => {
    const query = title.trim().toLowerCase();
    const now = new Date();
    let start: Date | null = null;
    if (datePreset === "today") start = startOfDay(now);
    if (datePreset === "week") {
      start = startOfDay(now);
      start.setDate(start.getDate() - 6);
    }
    if (datePreset === "month") {
      start = startOfDay(now);
      start.setDate(start.getDate() - 29);
    }

    const enabledIds = new Set(enabledTags.map((tag) => tag.id));
    return history.filter((c) => {
      if (c.number_of_messages <= 0) return false;
      const createdAt = new Date(c.created_at);
      if (start && createdAt < start) return false;
      if (selectedTags.length > 0 || untagged) {
        const matchesTag = (c.tags || []).some((tagId) => selectedTags.includes(tagId));
        const matchesUntagged = untagged && !hasEnabledTag(c, enabledIds);
        if (!matchesTag && !matchesUntagged) return false;
      }
      if (selectedAgents.length > 0) {
        if (!relatedAgentIds(c).some((agentId) => selectedAgents.includes(agentId))) {
          return false;
        }
      }
      if (query) {
        const haystack = `${c.title || ""} ${c.summary || ""}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [datePreset, enabledTags, history, selectedAgents, selectedTags, title, untagged]);

  const groups = useMemo(() => {
    const sorted = [...filteredHistory].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
    if (groupBy === "tag") {
      const enabledIds = new Set(enabledTags.map((tag) => tag.id));
      const result: ConversationGroup[] = [];
      enabledTags.forEach((tag) => {
        const items = sorted.filter((conversation) => conversation.tags?.includes(tag.id));
        if (items.length > 0) result.push({ key: `tag-${tag.id}`, label: tag.title, tag, items });
      });
      const withoutTags = sorted.filter((conversation) => !hasEnabledTag(conversation, enabledIds));
      if (withoutTags.length > 0) {
        result.push({ key: "no-tag", label: t("no-tag"), items: withoutTags });
      }
      return result;
    }
    if (groupBy === "agent") {
      const knownIds = new Set(namedAgents.map((agent) => agent.id));
      const result: ConversationGroup[] = [];
      namedAgents.forEach((agent) => {
        const items = sorted.filter((conversation) =>
          relatedAgentIds(conversation).includes(agent.id)
        );
        if (items.length > 0) result.push({ key: `agent-${agent.id}`, label: agent.name, items });
      });
      const unmatched = sorted.filter((conversation) => {
        const ids = relatedAgentIds(conversation);
        return ids.length === 0 || ids.every((id) => !knownIds.has(id));
      });
      if (unmatched.length > 0) {
        result.push({ key: "no-agent", label: t("no-agent"), items: unmatched });
      }
      return result;
    }
    const map = new Map<string, TConversation[]>();
    sorted.forEach((conversation) => {
      const key = dayKey(conversation.created_at);
      const list = map.get(key) || [];
      list.push(conversation);
      map.set(key, list);
    });
    return [...map.entries()].map(([key, items]) => ({
      key,
      label: formatDay(items[0].created_at, i18n.language),
      items,
    }));
  }, [enabledTags, filteredHistory, groupBy, i18n.language, namedAgents, t]);

  const toggleTag = (tagId: number) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    );
  };

  const toggleAgent = (agentId: number) => {
    setSelectedAgents((prev) =>
      prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]
    );
  };

  const toggleGroup = (key: string) => {
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const filterCount =
    (datePreset !== "any" ? 1 : 0) +
    (groupBy !== "date" ? 1 : 0) +
    selectedTags.length +
    (untagged ? 1 : 0) +
    selectedAgents.length;

  return (
    <AppPage
      title={
        <Group gap={8} wrap="nowrap" component="span">
          <IconMessage size={20} />
          {t("conversations")}
        </Group>
      }
    >
      <Box maw={1100} w="100%" mx="auto">
        <Stack gap="lg">
          <Group gap="sm" align="center" wrap="wrap">
            <TextInput
              placeholder={t("search-conversations-by")}
              value={title}
              leftSection={<IconSearch size={16} />}
              onChange={(e) => setTitle(e.currentTarget.value)}
              style={{ flex: "1 1 16rem" }}
            />
            <Box visibleFrom="sm">
              <DatePresetSelect value={datePreset} onChange={setDatePreset} fullWidth={false} t={t} />
            </Box>
            <Box visibleFrom="sm">
              <GroupBySelect value={groupBy} onChange={setGroupBy} fullWidth={false} t={t} />
            </Box>
            <Button
              hiddenFrom="sm"
              variant="default"
              leftSection={<IconFilter size={16} />}
              onClick={openFilters}
            >
              {filterCount > 0 ? `${t("filters")} (${filterCount})` : t("filters")}
            </Button>
          </Group>

          <Stack gap="md" visibleFrom="sm">
            <ChipFilters
              tags={enabledTags}
              agents={namedAgents}
              selectedTags={selectedTags}
              selectedAgents={selectedAgents}
              onToggleTag={toggleTag}
              untagged={untagged}
              onToggleUntagged={() => setUntagged((prev) => !prev)}
              onToggleAgent={toggleAgent}
              t={t}
            />
          </Stack>

          <Modal opened={filtersOpened} onClose={closeFilters} title={t("filters")}>
            <Stack gap="md">
              <DatePresetSelect value={datePreset} onChange={setDatePreset} fullWidth t={t} />
              <GroupBySelect value={groupBy} onChange={setGroupBy} fullWidth t={t} />
              <ChipFilters
                tags={enabledTags}
                agents={namedAgents}
                selectedTags={selectedTags}
                selectedAgents={selectedAgents}
                onToggleTag={toggleTag}
                untagged={untagged}
                onToggleUntagged={() => setUntagged((prev) => !prev)}
                onToggleAgent={toggleAgent}
                t={t}
              />
            </Stack>
          </Modal>

          {loading ? (
            <Group justify="center" py="xl">
              <Loader />
            </Group>
          ) : groups.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              {t("no-conversations")}
            </Text>
          ) : (
            <Stack gap="lg">
              {groups.map((group) => {
                const collapsed = collapsedGroups.has(group.key);
                return (
                <Stack key={group.key} gap="xs">
                  <UnstyledButton
                    onClick={() => toggleGroup(group.key)}
                    aria-expanded={!collapsed}
                  >
                    <Group gap={6} wrap="nowrap">
                      {collapsed ? <IconChevronRight size={14} /> : <IconChevronDown size={14} />}
                      {group.tag ? (
                        <TagChip tag={group.tag} />
                      ) : (
                        <Text size="sm" c="dimmed">
                          {group.label}
                        </Text>
                      )}
                      <Text size="xs" c="dimmed">
                        {group.items.length}
                      </Text>
                    </Group>
                  </UnstyledButton>
                  {!collapsed && group.items.map((conversation) => {
                    const tags = (conversation.tags || [])
                      .map((id) => tagById.get(id))
                      .filter((tag): tag is TTag => Boolean(tag))
                      .sort((a, b) => {
                        const aOn = selectedTags.includes(a.id) ? 0 : 1;
                        const bOn = selectedTags.includes(b.id) ? 0 : 1;
                        return aOn - bOn;
                      });
                    return (
                      <UnstyledButton
                        key={conversation.id}
                        component={Link}
                        to={`/chat?conversation=${conversation.id}`}
                        w="100%"
                        px="sm"
                        py="sm"
                        style={{ borderRadius: 12 }}
                        styles={{
                          root: {
                            "&:hover": {
                              background: "var(--mantine-color-dark-6)",
                            },
                          },
                        }}
                      >
                        <Group wrap="nowrap" gap="sm">
                          <Text fw={600} lineClamp={1} style={{ flex: 1, minWidth: 0 }}>
                            {conversation.title || conversation.id}
                          </Text>
                          {tags.length > 0 && (
                            <Group gap={4} wrap="nowrap" style={{ flexShrink: 0 }}>
                              {tags.slice(0, 4).map((tag) => (
                                <TagMark key={tag.id} tag={tag} />
                              ))}
                              {tags.length > 4 && (
                                <Text size="xs" c="dimmed">
                                  +{tags.length - 4}
                                </Text>
                              )}
                            </Group>
                          )}
                          <Text size="sm" c="dimmed" style={{ flexShrink: 0 }}>
                            {formatTime(conversation.created_at, i18n.language)}
                          </Text>
                        </Group>
                      </UnstyledButton>
                    );
                  })}
                </Stack>
                );
              })}
            </Stack>
          )}
        </Stack>
      </Box>
    </AppPage>
  );
}
