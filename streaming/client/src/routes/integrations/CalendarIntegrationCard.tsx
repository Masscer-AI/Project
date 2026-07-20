import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Badge,
  Button,
  Card,
  Group,
  Stack,
  Text,
} from "@mantine/core";
import { IconCalendar, IconPlugConnected } from "@tabler/icons-react";
import {
  connectIntegration,
  disconnectIntegration,
  getIntegrations,
  TIntegration,
} from "../../modules/apiCalls";

const GOOGLE_CALENDAR_PROVIDER = "google_calendar";

export const CalendarIntegrationCard = () => {
  const { t } = useTranslation();
  const [integrations, setIntegrations] = useState<TIntegration[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  const personalCalendar = useMemo(
    () =>
      integrations.find(
        (item) =>
          item.provider === GOOGLE_CALENDAR_PROVIDER && item.owner_type === "user"
      ),
    [integrations]
  );

  const loadIntegrations = useCallback(async () => {
    setLoading(true);
    try {
      const integrationsData = await getIntegrations();
      setIntegrations(integrationsData.integrations || []);
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void loadIntegrations();
  }, [loadIntegrations]);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      const returnTo = `${window.location.origin}/integrations?tab=calendar`;
      const data = await connectIntegration(
        GOOGLE_CALENDAR_PROVIDER,
        "user",
        returnTo
      );
      if (data.authorization_url) {
        window.location.href = data.authorization_url;
      }
    } catch {
      toast.error(t("integrations-connect-error"));
      setConnecting(false);
    }
  };

  const handleDisconnect = async () => {
    setDisconnecting(true);
    try {
      await disconnectIntegration(GOOGLE_CALENDAR_PROVIDER, "user");
      toast.success(t("integrations-disconnect-success"));
      await loadIntegrations();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      setDisconnecting(false);
    }
  };

  const isConnected = Boolean(personalCalendar?.connected);

  return (
    <Card withBorder padding="lg" radius="md">
      <Stack gap="md">
        <Group gap="sm">
          <IconCalendar size={28} />
          <Stack gap={0}>
            <Text fw={600}>{t("integrations-google-calendar")}</Text>
            <Text size="sm" c="dimmed">
              {t("integrations-google-calendar-desc")}
            </Text>
          </Stack>
        </Group>

        {!isConnected ? (
          <Button
            leftSection={<IconPlugConnected size={18} />}
            onClick={() => void handleConnect()}
            loading={connecting || loading}
          >
            {t("integrations-connect")}
          </Button>
        ) : (
          <Group justify="space-between" wrap="nowrap">
            <Stack gap={2}>
              <Text size="sm" fw={500}>
                {t("integrations-owner-me")}
              </Text>
              <Text size="xs" c="dimmed">
                {t("integrations-account")}:{" "}
                {personalCalendar?.account_email || personalCalendar?.account_label}
              </Text>
            </Stack>
            <Group gap="xs">
              <Badge color="green" variant="light">
                {t("integrations-connected")}
              </Badge>
              <Button
                size="xs"
                variant="subtle"
                color="red"
                loading={disconnecting}
                onClick={() => void handleDisconnect()}
              >
                {t("integrations-disconnect")}
              </Button>
            </Group>
          </Group>
        )}
      </Stack>
    </Card>
  );
};
