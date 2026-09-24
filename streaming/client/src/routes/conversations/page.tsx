import React, { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Box,
  Button,
  Group,
  Loader,
  Select,
  Stack,
  Text,
  TextInput,
  UnstyledButton,
} from "@mantine/core";
import { IconCalendar, IconMessage, IconPlus, IconSearch } from "@tabler/icons-react";
import { AppPage } from "../../components/AppPage/AppPage";
import { getAllConversations, getTags } from "../../modules/apiCalls";
import { TConversation, TTag } from "../../types";

type DatePreset = "any" | "today" | "week" | "month";

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

export default function ConversationsPage() {
  const { t, i18n } = useTranslation();
  const [history, setHistory] = useState<TConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [orgTags, setOrgTags] = useState<TTag[]>([]);
  const [title, setTitle] = useState("");
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [datePreset, setDatePreset] = useState<DatePreset>("any");

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

    return history.filter((c) => {
      if (c.number_of_messages <= 0) return false;
      const createdAt = new Date(c.created_at);
      if (start && createdAt < start) return false;
      if (selectedTags.length > 0) {
        if (!c.tags?.some((tagId) => selectedTags.includes(tagId))) return false;
      }
      if (query) {
        const haystack = `${c.title || ""} ${c.summary || ""}`.toLowerCase();
        if (!haystack.includes(query)) return false;
      }
      return true;
    });
  }, [datePreset, history, selectedTags, title]);

  const groups = useMemo(() => {
    const sorted = [...filteredHistory].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
    const map = new Map<string, TConversation[]>();
    sorted.forEach((conversation) => {
      const key = dayKey(conversation.created_at);
      const list = map.get(key) || [];
      list.push(conversation);
      map.set(key, list);
    });
    return [...map.entries()];
  }, [filteredHistory]);

  const toggleTag = (tagId: number) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    );
  };

  const enabledTags = orgTags.filter((tag) => tag.enabled);

  return (
    <AppPage
      title={t("conversations")}
      right={
        <Button
          component={Link}
          to="/chat"
          leftSection={<IconPlus size={16} />}
          variant="white"
          color="dark"
        >
          {t("new-conversation")}
        </Button>
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
            <Select
              value={datePreset}
              onChange={(value) => {
                if (
                  value === "any" ||
                  value === "today" ||
                  value === "week" ||
                  value === "month"
                ) {
                  setDatePreset(value);
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
              w={200}
            />
          </Group>

          {enabledTags.length > 0 && (
            <Group gap="xs" wrap="wrap">
              {enabledTags.map((tag) => {
                const active = selectedTags.includes(tag.id);
                return (
                  <UnstyledButton
                    key={tag.id}
                    onClick={() => toggleTag(tag.id)}
                    px="sm"
                    py={6}
                    style={{
                      borderRadius: 999,
                      border: `1px solid ${
                        active
                          ? tagDotColor(tag.color)
                          : "var(--mantine-color-dark-4)"
                      }`,
                    }}
                  >
                    <TagChip tag={tag} />
                  </UnstyledButton>
                );
              })}
            </Group>
          )}

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
              {groups.map(([key, items]) => (
                <Stack key={key} gap="xs">
                  <Text size="sm" c="dimmed">
                    {formatDay(items[0].created_at, i18n.language)}
                  </Text>
                  {items.map((conversation) => {
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
                          <Box
                            w={36}
                            h={36}
                            style={{
                              borderRadius: 10,
                              background: "var(--mantine-color-dark-6)",
                              display: "flex",
                              alignItems: "center",
                              justifyContent: "center",
                              flexShrink: 0,
                            }}
                          >
                            <IconMessage size={16} />
                          </Box>
                          <Text fw={600} lineClamp={1} style={{ flex: 1, minWidth: 0 }}>
                            {conversation.title || conversation.id}
                          </Text>
                          {tags[0] && <TagChip tag={tags[0]} />}
                          <Text size="sm" c="dimmed" style={{ flexShrink: 0 }}>
                            {formatTime(conversation.created_at, i18n.language)}
                          </Text>
                        </Group>
                      </UnstyledButton>
                    );
                  })}
                </Stack>
              ))}
            </Stack>
          )}
        </Stack>
      </Box>
    </AppPage>
  );
}
