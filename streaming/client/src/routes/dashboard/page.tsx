import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import {
  getAllConversations,
  getAlertStats,
  getUser,
} from "../../modules/apiCalls";
import { TConversation, TAlertStats } from "../../types";
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

export default function DashboardPage() {
  const { startup, setUser } = useStore((state) => ({
    startup: state.startup,
    setUser: state.setUser,
  }));
  const { t } = useTranslation();
  const [conversations, setConversations] = useState<TConversation[]>([]);
  const [alertStats, setAlertStats] = useState<TAlertStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const loadUser = async () => {
      try {
        const user = (await getUser()) as TUserData;
        setUser(user);
      } catch (error) {
        console.error("Error loading user:", error);
      }
    };

    loadUser();
    startup();
    loadConversations();
    loadAlertStats();
  }, []);

  const loadConversations = async () => {
    try {
      const data = await getAllConversations("org", { status: "all" });
      setConversations(data);
    } catch (error) {
      console.error("Error loading conversations:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const loadAlertStats = async () => {
    try {
      const stats = await getAlertStats();
      setAlertStats(stats);
    } catch (error) {
      console.error("Error loading alert stats:", error);
    }
  };

  return (
    <DashboardLayout>
      {isLoading ? (
        <Group justify="center" py="xl">
          <Loader />
        </Group>
      ) : (
        <Stack gap="xl">
          <DashboardStats
            conversations={conversations}
            alertStats={alertStats}
            t={t}
          />
          <Card withBorder padding="lg" radius="md">
            <ConversationsTable
              conversations={conversations || []}
              onConversationsChanged={loadConversations}
            />
          </Card>
        </Stack>
      )}
    </DashboardLayout>
  );
}

// ─── Stats ──────────────────────────────────────────────────────────────────────

function DashboardStats({
  conversations,
  alertStats,
  t,
}: {
  conversations: TConversation[];
  alertStats: TAlertStats | null;
  t: any;
}) {
  const totalConversations = conversations.length;
  const totalMessages = conversations.reduce(
    (sum, conv) => sum + (conv.number_of_messages || 0),
    0
  );

  const topUsers = React.useMemo(() => {
    const byUser = new Map<
      string,
      { label: string; conversations: number; messages: number }
    >();
    conversations.forEach((conv) => {
      if (conv.user_id == null) return;
      const key = String(conv.user_id);
      const label = conv.user_username || `${t("user")} ${conv.user_id}`;
      const prev = byUser.get(key) || { label, conversations: 0, messages: 0 };
      prev.conversations += 1;
      prev.messages += conv.number_of_messages || 0;
      byUser.set(key, prev);
    });
    return Array.from(byUser.values())
      .sort((a, b) => {
        if (b.conversations !== a.conversations) {
          return b.conversations - a.conversations;
        }
        return b.messages - a.messages;
      })
      .slice(0, 5);
  }, [conversations, t]);

  const weekData = React.useMemo(() => {
    const now = new Date();
    const points = Array.from({ length: 7 }, (_, idx) => {
      const day = new Date(now);
      day.setHours(0, 0, 0, 0);
      day.setDate(now.getDate() - (6 - idx));
      return { date: day, count: 0 };
    });

    conversations.forEach((conv) => {
      const convDate = new Date(conv.created_at);
      convDate.setHours(0, 0, 0, 0);
      const match = points.find((p) => p.date.getTime() === convDate.getTime());
      if (match) match.count += 1;
    });

    return points;
  }, [conversations]);
  const recentConversations = weekData.reduce((sum, p) => sum + p.count, 0);
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
