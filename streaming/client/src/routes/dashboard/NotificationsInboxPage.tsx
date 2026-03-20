import React, { useCallback, useEffect, useState } from "react";
import { useStore } from "../../modules/store";
import { getMyNotifications, markNotificationRead } from "../../modules/apiCalls";
import { TUserNotification } from "../../types";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";
import { DashboardLayout } from "./DashboardLayout";
import {
  Badge,
  Button,
  Card,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconCheck } from "@tabler/icons-react";

function notifyInboxUpdated() {
  window.dispatchEvent(new CustomEvent("masscer:notifications-updated"));
}

export default function NotificationsInboxPage() {
  const { startup } = useStore((state) => ({ startup: state.startup }));
  const { t } = useTranslation();
  const [items, setItems] = useState<TUserNotification[]>([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const data = await getMyNotifications();
      setItems(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    startup();
    load();
  }, [startup, load]);

  const handleMarkRead = async (id: string) => {
    try {
      await markNotificationRead(id);
      setItems((prev) =>
        prev.map((n) =>
          n.id === id ? { ...n, read_at: new Date().toISOString() } : n
        )
      );
      notifyInboxUpdated();
    } catch (e) {
      console.error(e);
    }
  };

  const unread = items.filter((n) => !n.read_at);

  return (
    <DashboardLayout>
      <Stack gap="lg">
        <Title order={2} ta="center">
          {t("notifications-inbox") || "Notifications"}
        </Title>

        {loading ? (
          <Group justify="center" py="xl">
            <Loader />
          </Group>
        ) : items.length === 0 ? (
          <Text ta="center" c="dimmed" py="xl">
            {t("no-notifications-yet") || "No notifications yet."}
          </Text>
        ) : (
          <Stack gap="sm">
            {unread.length > 0 && (
              <Text size="sm" c="dimmed" ta="center">
                {t("unread-count", { count: unread.length }) ||
                  `${unread.length} unread`}
              </Text>
            )}
            {items.map((n) => (
              <Card
                key={n.id}
                withBorder
                padding="md"
                radius="md"
                opacity={n.read_at ? 0.75 : 1}
              >
                <Group justify="space-between" align="flex-start" wrap="nowrap">
                  <Stack gap={4} style={{ flex: 1, minWidth: 0 }}>
                    {!n.read_at && (
                      <Badge size="xs" color="red" variant="filled">
                        {t("new") || "New"}
                      </Badge>
                    )}
                    <Text size="sm">{n.message}</Text>
                    <Text size="xs" c="dimmed">
                      {new Date(n.created_at).toLocaleString()}
                    </Text>
                    <Text
                      component={Link}
                      to="/dashboard/alerts"
                      size="xs"
                      c="violet"
                      style={{ textDecoration: "underline" }}
                    >
                      {t("open-alerts-dashboard") || "View alerts"}
                    </Text>
                  </Stack>
                  {!n.read_at && (
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconCheck size={14} />}
                      onClick={() => handleMarkRead(n.id)}
                    >
                      {t("mark-read") || "Read"}
                    </Button>
                  )}
                </Group>
              </Card>
            ))}
          </Stack>
        )}
      </Stack>
    </DashboardLayout>
  );
}
