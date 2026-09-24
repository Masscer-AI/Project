import React, { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Stack,
  Text,
  TextInput,
  UnstyledButton,
} from "@mantine/core";
import { DatePickerInput } from "@mantine/dates";
import { IconSearch } from "@tabler/icons-react";
import { AppHeader } from "../../components/AppHeader/AppHeader";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { getAllConversations, getTags } from "../../modules/apiCalls";
import { TConversation, TTag } from "../../types";

function formatDate(iso: string, locale: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(d);
}

export default function ConversationsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const chatState = useStore((s) => s.chatState);
  const [history, setHistory] = useState<TConversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [orgTags, setOrgTags] = useState<TTag[]>([]);
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
    const query = filters.title.toLowerCase();
    return history.filter((c) => {
      if (c.number_of_messages <= 0) return false;

      const createdAtDate = new Date(c.created_at);
      const start = filters.startDate ? new Date(filters.startDate) : null;
      if (start) start.setHours(0, 0, 0, 0);
      const end = filters.endDate ? new Date(filters.endDate) : null;
      if (end) end.setHours(23, 59, 59, 999);
      if (start && createdAtDate < start) return false;
      if (end && createdAtDate > end) return false;

      if (filters.tags.length > 0) {
        if (!c.tags?.some((tagId) => filters.tags.includes(tagId))) return false;
      }

      if (query) {
        const title = (c.title || "").toLowerCase();
        if (!title.includes(query)) return false;
      }

      return true;
    });
  }, [filters, history]);

  const today = new Date().toLocaleDateString();
  const todayItems = filteredHistory.filter(
    (c) => new Date(c.created_at).toLocaleDateString() === today
  );
  const previousItems = filteredHistory.filter(
    (c) => new Date(c.created_at).toLocaleDateString() !== today
  );

  const filterByTag = (tagId: number) => {
    setFilters((prev) => ({
      ...prev,
      tags: prev.tags.includes(tagId)
        ? prev.tags.filter((id) => id !== tagId)
        : [...prev.tags, tagId],
    }));
  };

  const renderRow = (conversation: TConversation) => {
    const tags = (conversation.tags || [])
      .map((id) => tagById.get(id))
      .filter((tag): tag is TTag => Boolean(tag));
    return (
      <UnstyledButton
        key={conversation.id}
        onClick={() => navigate(`/chat?conversation=${conversation.id}`)}
        w="100%"
      >
        <Card withBorder padding="md" radius="md">
          <Group justify="space-between" align="flex-start" wrap="nowrap" gap="md">
            <Stack gap={6} style={{ flex: 1, minWidth: 0 }}>
              <Text fw={600} lineClamp={2}>
                {conversation.title || conversation.id}
              </Text>
              {tags.length > 0 && (
                <Group gap="xs" wrap="wrap">
                  {tags.map((tag) => (
                    <Badge
                      key={tag.id}
                      size="sm"
                      variant="outline"
                      color={tag.color || "violet"}
                    >
                      {tag.title}
                    </Badge>
                  ))}
                </Group>
              )}
            </Stack>
            <Text size="sm" c="dimmed" style={{ flexShrink: 0 }}>
              {formatDate(conversation.created_at, i18n.language)}
            </Text>
          </Group>
        </Card>
      </UnstyledButton>
    );
  };

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          padding: 24,
          overflowY: "auto",
          minHeight: "100vh",
          display: "flex",
          flexDirection: "column",
        }}
        className="relative"
      >
        <AppHeader title={t("conversations")} />

        <Box maw={1100} w="100%" mx="auto">
          <Stack gap="lg">
            <Stack gap="xs">
              <TextInput
                placeholder={t("filter-conversations")}
                value={filters.title}
                leftSection={<IconSearch size={16} />}
                onChange={(e) => {
                  const val = e.currentTarget.value;
                  setFilters((prev) => ({ ...prev, title: val }));
                }}
                radius="md"
              />
              <Group gap="xs" grow preventGrowOverflow wrap="wrap">
                <DatePickerInput
                  style={{ minWidth: 0, flex: 1 }}
                  value={filters.startDate}
                  onChange={(val) =>
                    setFilters((prev) => ({
                      ...prev,
                      startDate: val as Date | null,
                    }))
                  }
                  placeholder={t("start-date")}
                  clearable
                />
                <DatePickerInput
                  style={{ minWidth: 0, flex: 1 }}
                  value={filters.endDate}
                  onChange={(val) =>
                    setFilters((prev) => ({
                      ...prev,
                      endDate: val as Date | null,
                    }))
                  }
                  placeholder={t("end-date")}
                  clearable
                />
              </Group>
              {orgTags.filter((tag) => tag.enabled).length > 0 && (
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
              )}
              <Group justify="flex-end">
                <Button
                  size="xs"
                  variant="default"
                  onClick={() =>
                    setFilters({
                      tags: [],
                      startDate: null,
                      endDate: null,
                      title: "",
                    })
                  }
                >
                  {t("clean-filters")}
                </Button>
              </Group>
            </Stack>

            {loading ? (
              <Group justify="center" py="xl">
                <Loader />
              </Group>
            ) : filteredHistory.length === 0 ? (
              <Text c="dimmed" ta="center" py="xl">
                {t("no-conversations")}
              </Text>
            ) : (
              <Stack gap="lg">
                {todayItems.length > 0 && (
                  <Stack gap="xs">
                    <Text size="sm" fw={600}>
                      {t("today")}
                    </Text>
                    {todayItems.map(renderRow)}
                  </Stack>
                )}
                {previousItems.length > 0 && (
                  <Stack gap="xs">
                    <Text size="sm" fw={600}>
                      {t("previous-days")}
                    </Text>
                    {previousItems.map(renderRow)}
                  </Stack>
                )}
              </Stack>
            )}
          </Stack>
        </Box>
      </div>
    </main>
  );
}
