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
  Button,
  Card,
  Group,
  Loader,
  SimpleGrid,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import {
  IconMessage,
  IconMail,
  IconCalendar,
  IconAlertTriangle,
  IconCircleCheck,
  IconBell,
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
  const [showTable, setShowTable] = useState(false);

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
      const data = await getAllConversations();
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

          <Group justify="center">
            <Button
              variant="default"
              onClick={() => setShowTable(!showTable)}
            >
              {showTable
                ? t("hide-table")
                : t("view-all-conversations")}
            </Button>
          </Group>

          {showTable && (
            <Card withBorder padding="lg" radius="md">
              <ConversationsTable conversations={conversations || []} />
            </Card>
          )}
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
  const recentConversations = conversations.filter((conv) => {
    const date = new Date(conv.created_at);
    const weekAgo = new Date();
    weekAgo.setDate(weekAgo.getDate() - 7);
    return date >= weekAgo;
  }).length;

  const stats = [
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
    {
      icon: <IconCalendar size={28} />,
      label: t("this-week"),
      value: recentConversations,
    },
  ];

  if (alertStats) {
    stats.push(
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
      }
    );
  }

  return (
    <SimpleGrid cols={{ base: 2, lg: 3 }} spacing="md">
      {stats.map((stat) => (
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
  );
}
