import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Badge,
  Button,
  Card,
  Group,
  SegmentedControl,
  Stack,
  Text,
} from "@mantine/core";
import { IconCalendar, IconPlugConnected } from "@tabler/icons-react";
import {
  connectIntegration,
  disconnectIntegration,
  getIntegrations,
  getUserOrganizations,
  IntegrationOwnerType,
  TIntegration,
} from "../../modules/apiCalls";
import { TOrganization } from "../../types";

const GOOGLE_CALENDAR_PROVIDER = "google_calendar";

export const CalendarIntegrationCard = () => {
  const { t } = useTranslation();
  const [integrations, setIntegrations] = useState<TIntegration[]>([]);
  const [organizations, setOrganizations] = useState<TOrganization[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState<IntegrationOwnerType | null>(null);
  const [ownerScope, setOwnerScope] = useState<IntegrationOwnerType>("user");

  const organizationName = organizations[0]?.name || "";
  const hasOrganization = organizations.length > 0;

  const calendarByOwner = useMemo(() => {
    const map: Partial<Record<IntegrationOwnerType, TIntegration>> = {};
    for (const item of integrations) {
      if (item.provider === GOOGLE_CALENDAR_PROVIDER) {
        map[item.owner_type] = item;
      }
    }
    return map;
  }, [integrations]);

  const loadIntegrations = useCallback(async () => {
    setLoading(true);
    try {
      const [integrationsData, orgs] = await Promise.all([
        getIntegrations(),
        getUserOrganizations().catch(() => [] as TOrganization[]),
      ]);
      setIntegrations(integrationsData.integrations || []);
      setOrganizations(orgs || []);
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
    if (ownerScope === "organization" && !hasOrganization) {
      toast.error(t("integrations-no-organization"));
      return;
    }
    setConnecting(true);
    try {
      const returnTo = `${window.location.origin}/integrations?tab=calendar`;
      const data = await connectIntegration(
        GOOGLE_CALENDAR_PROVIDER,
        ownerScope,
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

  const handleDisconnect = async (owner: IntegrationOwnerType) => {
    setDisconnecting(owner);
    try {
      await disconnectIntegration(GOOGLE_CALENDAR_PROVIDER, owner);
      toast.success(t("integrations-disconnect-success"));
      await loadIntegrations();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      setDisconnecting(null);
    }
  };

  const renderConnectedOwner = (owner: IntegrationOwnerType, label: string) => {
    const integration = calendarByOwner[owner];
    if (!integration?.connected) return null;

    return (
      <Group key={owner} justify="space-between" wrap="nowrap">
        <Stack gap={2}>
          <Text size="sm" fw={500}>
            {label}
          </Text>
          <Text size="xs" c="dimmed">
            {t("integrations-account")}: {integration.account_email || integration.account_label}
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
            loading={disconnecting === owner}
            onClick={() => void handleDisconnect(owner)}
          >
            {t("integrations-disconnect")}
          </Button>
        </Group>
      </Group>
    );
  };

  const hasConnectedCalendar =
    Boolean(calendarByOwner.user?.connected) ||
    Boolean(calendarByOwner.organization?.connected);

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

        <SegmentedControl
          value={ownerScope}
          onChange={(v) => setOwnerScope(v as IntegrationOwnerType)}
          data={[
            { label: t("integrations-owner-me"), value: "user" },
            {
              label: hasOrganization
                ? `${t("integrations-owner-organization")}${organizationName ? `: ${organizationName}` : ""}`
                : t("integrations-owner-organization"),
              value: "organization",
              disabled: !hasOrganization,
            },
          ]}
        />

        <Button
          leftSection={<IconPlugConnected size={18} />}
          onClick={() => void handleConnect()}
          loading={connecting || loading}
          disabled={ownerScope === "organization" && !hasOrganization}
        >
          {t("integrations-connect")}
        </Button>

        {hasConnectedCalendar && (
          <Stack gap="sm">
            {renderConnectedOwner("user", t("integrations-owner-me"))}
            {hasOrganization &&
              renderConnectedOwner(
                "organization",
                `${t("integrations-owner-organization")}${organizationName ? `: ${organizationName}` : ""}`
              )}
          </Stack>
        )}
      </Stack>
    </Card>
  );
};
