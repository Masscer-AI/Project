import React, { useState, useEffect, useCallback } from "react";
import { useStore } from "../../modules/store";
import {
  getConversations,
  getConversationStats,
  getAlertStats,
  getUser,
} from "../../modules/apiCalls";
import type {
  TConversationFilters,
  TConversationsResponse,
  TConversationStats,
} from "../../modules/apiCalls";
import { TAlertStats } from "../../types";
import { TUserData } from "../../types/chatTypes";
import { useTranslation } from "react-i18next";
import { DashboardLayout } from "./DashboardLayout";
import { ConversationsTable } from "./ConversationsTable";
import {
  Badge,
  Card,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Tooltip,
  Title,
} from "@mantine/core";
import {
  IconMessage,
  IconMail,
  IconCalendar,
  IconAlertTriangle,
  IconCircleCheck,
  IconBell,
  IconUsers,
} from "@tabler/icons-react";

const DEFAULT_FILTERS: TConversationFilters = {
  scope: "org",
  status: "all",
  sortBy: "newest",
  search: "",
  userId: "",
  dateFrom: null,
  dateTo: null,
  minMessages: 1,
  maxMessages: "" as unknown as number,
  selectedTags: [],
  selectedAlertRules: [],
  chatWidgetId: "",
  messagesSort: "none",
};

export default function DashboardPage() {
  const { startup, setUser } = useStore((state) => ({
    startup: state.startup,
    setUser: state.setUser,
  }));
  const { t } = useTranslation();
  const [convStats, setConvStats] = useState<TConversationStats | null>(null);
  const [alertStats, setAlertStats] = useState<TAlertStats | null>(null);
  const [conversationsData, setConversationsData] = useState<
    TConversationsResponse | null
  >(null);
  const [filters, setFilters] = useState<TConversationFilters>(DEFAULT_FILTERS);
  const [page, setPage] = useState(0);
  const [isLoadingStats, setIsLoadingStats] = useState(true);
  const [isLoadingConversations, setIsLoadingConversations] = useState(true);

  const loadUser = useCallback(async () => {
    try {
      const user = (await getUser()) as TUserData;
      setUser(user);
    } catch (error) {
      console.error("Error loading user:", error);
    }
  }, [setUser]);

  useEffect(() => {
    loadUser();
    startup();
  }, [loadUser, startup]);

  const loadStats = useCallback(async () => {
    setIsLoadingStats(true);
    try {
      const [conv, alerts] = await Promise.all([
        getConversationStats(filters),
        getAlertStats(),
      ]);
      setConvStats(conv);
      setAlertStats(alerts);
    } catch (error) {
      console.error("Error loading stats:", error);
    } finally {
      setIsLoadingStats(false);
    }
  }, [filters]);

  const loadConversations = useCallback(async () => {
    setIsLoadingConversations(true);
    try {
      const data = await getConversations(filters, page, 50);
      setConversationsData(data);
    } catch (error) {
      console.error("Error loading conversations:", error);
    } finally {
      setIsLoadingConversations(false);
    }
  }, [filters, page]);

  useEffect(() => {
    loadStats();
  }, [loadStats]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const handleFiltersChange = useCallback((newFilters: TConversationFilters) => {
    setFilters(newFilters);
    setPage(0);
  }, []);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  const handleConversationsChanged = useCallback(() => {
    loadStats();
    loadConversations();
  }, [loadStats, loadConversations]);

  const isLoading = isLoadingStats && isLoadingConversations;

  return (
    <DashboardLayout>
      {isLoading && !convStats ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : (
        <Stack gap="xl">
          <DashboardStats
            convStats={convStats}
            alertStats={alertStats}
            isLoading={isLoadingStats}
            t={t}
          />
          <Card withBorder padding="lg" radius="md">
            <ConversationsTable
              conversations={conversationsData?.results ?? []}
              total={conversationsData?.total ?? 0}
              page={page}
              pageSize={50}
              filters={filters}
              filterOptions={conversationsData?.filter_options}
              onFiltersChange={handleFiltersChange}
              onPageChange={handlePageChange}
              onConversationsChanged={handleConversationsChanged}
              isLoading={isLoadingConversations}
            />
          </Card>
        </Stack>
      )}
    </DashboardLayout>
  );
}

// ─── Stats ──────────────────────────────────────────────────────────────────────

function DashboardStats({
  convStats,
  alertStats,
  isLoading,
  t,
}: {
  convStats: TConversationStats | null;
  alertStats: TAlertStats | null;
  isLoading: boolean;
  t: (key: string) => string;
}) {
  const totalConversations = convStats?.total_conversations ?? 0;
  const totalMessages = convStats?.total_messages ?? 0;
  const topUsers = convStats?.top_users ?? [];
  const weekBreakdown = convStats?.last_7_days_breakdown ?? [];
  const recentConversations = convStats?.last_7_days ?? 0;

  const weekData = React.useMemo(() => {
    const now = new Date();
    return Array.from({ length: 7 }, (_, idx) => {
      const day = new Date(now);
      day.setHours(0, 0, 0, 0);
      day.setDate(now.getDate() - (6 - idx));
      const dateStr = day.toISOString().slice(0, 10);
      const point = weekBreakdown.find((p) => p.date === dateStr);
      return { date: day, count: point?.count ?? 0 };
    });
  }, [weekBreakdown]);
  const maxWeekCount = Math.max(...weekData.map((p) => p.count), 1);
  const summaryStats = [
    {
      icon: <IconMessage size={28} />,
      label: t("total-conversations"),
      value: totalConversations,
    },
    {
      icon: <IconMail size={28} />,
      label: t("total-messages"),
      value: totalMessages,
    },
    ...(alertStats
      ? [
          {
            icon: <IconAlertTriangle size={28} />,
            label: t("pending-alerts"),
            value: alertStats.pending,
          },
          {
            icon: <IconCircleCheck size={28} />,
            label: t("resolved-alerts"),
            value: alertStats.resolved,
          },
          {
            icon: <IconBell size={28} />,
            label: t("total-alerts"),
            value: alertStats.total,
          },
        ]
      : []),
  ];

  return (
    <Stack gap="md">
      <SimpleGrid cols={{ base: 2, lg: 5 }} spacing="md">
        {summaryStats.map((stat) => (
          <Card key={stat.label} withBorder padding="lg" radius="md">
            <Group gap="md" wrap="nowrap">
              <Text c="violet">{stat.icon}</Text>
              <div>
                <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                  {stat.label}
                </Text>
                <Title order={2}>{stat.value}</Title>
              </div>
            </Group>
          </Card>
        ))}
      </SimpleGrid>

      <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
        <Card withBorder padding="lg" radius="md">
          <Group gap="md" wrap="nowrap" align="flex-start">
            <Text c="violet" mt={4}>
              <IconCalendar size={28} />
            </Text>
            <div style={{ width: "100%" }}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                {t("this-week")}
              </Text>
              <Title order={2}>{recentConversations}</Title>
              <div style={{ marginTop: 8 }}>
                <Group gap={6} align="end" wrap="nowrap">
                  {weekData.map((point, idx) => (
                    <Tooltip
                      key={idx}
                      withArrow
                      label={`${point.date.toLocaleDateString(undefined, {
                        weekday: "short",
                        month: "short",
                        day: "numeric",
                      })}: ${point.count} conversation${point.count === 1 ? "" : "s"}`}
                    >
                      <div
                        style={{
                          flex: 1,
                          height: 28,
                          background: "var(--mantine-color-dark-6)",
                          borderRadius: 4,
                          position: "relative",
                          overflow: "hidden",
                          cursor: "pointer",
                        }}
                      >
                        <div
                          style={{
                            position: "absolute",
                            left: 0,
                            right: 0,
                            bottom: 0,
                            height: `${Math.max((point.count / maxWeekCount) * 100, point.count > 0 ? 18 : 0)}%`,
                            background: "var(--mantine-color-violet-6)",
                            borderRadius: 4,
                          }}
                        />
                      </div>
                    </Tooltip>
                  ))}
                </Group>
                <Text size="xs" c="dimmed" mt={4}>
                  {recentConversations} {t("total-in-last-7-days")}
                </Text>
              </div>
            </div>
          </Group>
        </Card>

        <Card withBorder padding="lg" radius="md">
          <Group gap="md" wrap="nowrap" align="flex-start">
            <Text c="violet" mt={4}>
              <IconUsers size={28} />
            </Text>
            <div style={{ width: "100%" }}>
              <Text size="xs" c="dimmed" tt="uppercase" fw={500}>
                {t("most-active-users")}
              </Text>
              {topUsers.length === 0 ? (
                <Text size="sm" c="dimmed" mt={8}>
                  {t("no-user-activity-yet")}
                </Text>
              ) : (
                <Group gap={8} mt={8} wrap="wrap">
                  {topUsers.map((user) => (
                    <Badge key={user.label} variant="light" color="blue">
                      {user.label} ({user.conversations})
                    </Badge>
                  ))}
                </Group>
              )}
            </div>
          </Group>
        </Card>
      </SimpleGrid>
    </Stack>
  );
}
