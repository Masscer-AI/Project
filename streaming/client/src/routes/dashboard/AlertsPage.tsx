import React, { useState, useEffect } from "react";
import { useStore } from "../../modules/store";
import { getAlerts, updateAlertStatus } from "../../modules/apiCalls";
import { TConversationAlert } from "../../types";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { DashboardLayout } from "./DashboardLayout";
import {
  Anchor,
  Badge,
  Button,
  Card,
  Divider,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconEye, IconEyeOff } from "@tabler/icons-react";

export default function AlertsPage() {
  const { startup } = useStore((state) => ({
    startup: state.startup,
  }));
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<TConversationAlert[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState<
    "all" | "pending" | "notified" | "resolved" | "dismissed"
  >("all");

  useEffect(() => {
    startup();
  }, []);

  useEffect(() => {
    loadAlerts();
  }, [statusFilter]);

  const loadAlerts = async () => {
    try {
      setIsLoading(true);
      const data = await getAlerts(statusFilter);
      setAlerts(data);
    } catch (error) {
      console.error("Error loading alerts:", error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleStatusChange = async (
    alertId: string,
    newStatus: "RESOLVED" | "DISMISSED"
  ) => {
    try {
      await updateAlertStatus(alertId, newStatus);
      loadAlerts();
    } catch (error) {
      console.error("Error updating alert status:", error);
    }
  };

  const handleViewConversation = (conversationId: string) => {
    navigate(`/chat?conversation=${conversationId}`);
  };

  const filterOptions: {
    value: typeof statusFilter;
    label: string;
  }[] = [
    { value: "all", label: t("all") },
    { value: "pending", label: t("pending") },
    { value: "notified", label: t("notified") },
    { value: "resolved", label: t("resolved") },
    { value: "dismissed", label: t("dismissed") },
  ];

  return (
    <DashboardLayout>
      <Stack gap="lg">
        <Title order={2} ta="center">
          {t("alerts")}
        </Title>

        <Group justify="center" wrap="wrap" gap="xs">
          {filterOptions.map((opt) => (
            <Button
              key={opt.value}
              variant={statusFilter === opt.value ? "filled" : "default"}
              size="xs"
              onClick={() => setStatusFilter(opt.value)}
            >
              {opt.label}
            </Button>
          ))}
        </Group>

        {isLoading ? (
          <Group justify="center" py="xl">
            <Loader />
          </Group>
        ) : alerts.length === 0 ? (
          <Text ta="center" c="dimmed" py="xl" size="lg">
            {t("no-alerts-found")}
          </Text>
        ) : (
          <Stack gap="md" maw={900} mx="auto" w="100%">
            {alerts.map((alert) => (
              <AlertCard
                key={alert.id}
                alert={alert}
                onStatusChange={handleStatusChange}
                onViewConversation={handleViewConversation}
                t={t}
              />
            ))}
          </Stack>
        )}
      </Stack>
    </DashboardLayout>
  );
}

interface AlertCardProps {
  alert: TConversationAlert;
  onStatusChange: (alertId: string, status: "RESOLVED" | "DISMISSED") => void;
  onViewConversation: (conversationId: string) => void;
  t: any;
}

function AlertCard({
  alert,
  onStatusChange,
  onViewConversation,
  t,
}: AlertCardProps) {
  const [showDetails, setShowDetails] = useState(false);

  const getStatusColor = (status: string) => {
    switch (status) {
      case "PENDING":
        return "orange";
      case "NOTIFIED":
        return "blue";
      case "RESOLVED":
        return "green";
      case "DISMISSED":
        return "gray";
      default:
        return "gray";
    }
  };

  return (
    <Card withBorder padding="lg" radius="md">
      <Stack gap="sm">
        <Group justify="space-between" wrap="wrap">
          <Group gap="sm" wrap="wrap">
            <Text fw={600}>{alert.title}</Text>
            <Badge color={getStatusColor(alert.status)} size="sm">
              {t(alert.status.toLowerCase())}
            </Badge>
          </Group>
          <Text size="xs" c="dimmed">
            {new Date(alert.created_at).toLocaleDateString()}{" "}
            {new Date(alert.created_at).toLocaleTimeString()}
          </Text>
        </Group>

        <Stack gap={4}>
          <Text size="sm">
            <Text span fw={500}>
              {t("rule")}:
            </Text>{" "}
            {alert.alert_rule.name}
          </Text>
          <Text size="sm">
            <Text span fw={500}>
              {t("conversation")}:
            </Text>{" "}
            <Anchor
              size="sm"
              onClick={() => onViewConversation(alert.conversation_id)}
            >
              {alert.conversation_title ||
                alert.conversation_id.slice(0, 8)}
            </Anchor>
          </Text>
        </Stack>

        <Button
          variant="subtle"
          color="gray"
          size="compact-xs"
          leftSection={
            showDetails ? <IconEyeOff size={14} /> : <IconEye size={14} />
          }
          onClick={() => setShowDetails(!showDetails)}
          w="fit-content"
        >
          {showDetails ? t("hide-details") : t("show-details")}
        </Button>

        {showDetails && (
          <>
            <Divider />
            <Stack gap="sm">
              <div>
                <Text size="sm" fw={500} c="dimmed" mb={4}>
                  {t("ai-analysis")}
                </Text>
                <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
                  {alert.reasoning}
                </Text>
              </div>

              {Object.keys(alert.extractions).length > 0 && (
                <div>
                  <Text size="sm" fw={500} c="dimmed" mb={4}>
                    {t("extracted-data")}
                  </Text>
                  <Stack gap={4}>
                    {Object.entries(alert.extractions).map(([key, value]) => (
                      <Card key={key} padding="xs" radius="sm" withBorder>
                        <Text size="sm">
                          <Text span c="violet" fw={500}>
                            {key}:
                          </Text>{" "}
                          {typeof value === "object"
                            ? JSON.stringify(value)
                            : String(value)}
                        </Text>
                      </Card>
                    ))}
                  </Stack>
                </div>
              )}

              {alert.resolved_by_username && (
                <Text size="sm" c="dimmed">
                  <Text span fw={500}>
                    {t("resolved-by")}:
                  </Text>{" "}
                  {alert.resolved_by_username}
                </Text>
              )}

              {alert.dismissed_by_username && (
                <Text size="sm" c="dimmed">
                  <Text span fw={500}>
                    {t("dismissed-by")}:
                  </Text>{" "}
                  {alert.dismissed_by_username}
                </Text>
              )}
            </Stack>
          </>
        )}

        {(alert.status === "PENDING" || alert.status === "NOTIFIED") && (
          <>
            <Divider />
            <Group gap="xs">
              <Button
                variant="default"
                size="xs"
                color="green"
                onClick={() => onStatusChange(alert.id, "RESOLVED")}
              >
                {t("resolve")}
              </Button>
              <Button
                variant="default"
                size="xs"
                onClick={() => onStatusChange(alert.id, "DISMISSED")}
              >
                {t("dismiss")}
              </Button>
            </Group>
          </>
        )}
      </Stack>
    </Card>
  );
}
