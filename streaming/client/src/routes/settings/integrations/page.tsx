import React, { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  SegmentedControl,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconBrandGoogleDrive, IconMenu2, IconPlugConnected } from "@tabler/icons-react";
import { Sidebar } from "../../../components/Sidebar/Sidebar";
import { useStore } from "../../../modules/store";
import {
  connectIntegration,
  disconnectIntegration,
  getIntegrations,
  getUser,
  getUserOrganizations,
  IntegrationOwnerType,
  TIntegration,
} from "../../../modules/apiCalls";
import { TOrganization } from "../../../types";

const GOOGLE_DRIVE_PROVIDER = "google_drive";

export default function IntegrationsPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { chatState, toggleSidebar, user, setUser } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
    user: s.user,
    setUser: s.setUser,
  }));

  const [integrations, setIntegrations] = useState<TIntegration[]>([]);
  const [organizations, setOrganizations] = useState<TOrganization[]>([]);
  const [loading, setLoading] = useState(true);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState<IntegrationOwnerType | null>(null);
  const [ownerScope, setOwnerScope] = useState<IntegrationOwnerType>("user");

  const organizationName = organizations[0]?.name || "";

  const hasOrganization = organizations.length > 0;

  const driveByOwner = useMemo(() => {
    const map: Partial<Record<IntegrationOwnerType, TIntegration>> = {};
    for (const item of integrations) {
      if (item.provider === GOOGLE_DRIVE_PROVIDER) {
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
    if (!user) {
      getUser().then((data) => setUser(data)).catch(() => undefined);
    }
  }, [user, setUser]);

  useEffect(() => {
    loadIntegrations();
  }, [loadIntegrations]);

  useEffect(() => {
    const error = searchParams.get("error");
    if (error) {
      toast.error(t("integrations-connect-error"));
      searchParams.delete("error");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, t]);

  const handleConnect = async () => {
    if (ownerScope === "organization" && !hasOrganization) {
      toast.error(t("integrations-no-organization"));
      return;
    }
    setConnecting(true);
    try {
      const data = await connectIntegration(GOOGLE_DRIVE_PROVIDER, ownerScope);
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
      await disconnectIntegration(GOOGLE_DRIVE_PROVIDER, owner);
      toast.success(t("integrations-disconnect-success"));
      await loadIntegrations();
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      setDisconnecting(null);
    }
  };

  const renderOwnerStatus = (owner: IntegrationOwnerType, label: string) => {
    const integration = driveByOwner[owner];
    const connected = Boolean(integration?.connected);

    return (
      <Group key={owner} justify="space-between" wrap="nowrap">
        <Stack gap={2}>
          <Text size="sm" fw={500}>
            {label}
          </Text>
          {connected ? (
            <Text size="xs" c="dimmed">
              {t("integrations-account")}: {integration?.account_email || integration?.account_label}
            </Text>
          ) : (
            <Text size="xs" c="dimmed">
              {t("integrations-not-connected")}
            </Text>
          )}
        </Stack>
        <Group gap="xs">
          <Badge color={connected ? "green" : "gray"} variant="light">
            {connected ? t("integrations-connected") : t("integrations-not-connected")}
          </Badge>
          {connected && (
            <Button
              size="xs"
              variant="subtle"
              color="red"
              loading={disconnecting === owner}
              onClick={() => handleDisconnect(owner)}
            >
              {t("integrations-disconnect")}
            </Button>
          )}
        </Group>
      </Group>
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
          justifyContent: "center",
        }}
        className="relative"
      >
        {!chatState.isSidebarOpened && (
          <Box pos="absolute" top={24} left={24} style={{ zIndex: 10 }}>
            <ActionIcon variant="subtle" color="gray" onClick={toggleSidebar}>
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Stack maw={640} w="100%" gap="lg" mt={48}>
          <Stack gap={4}>
            <Title order={2}>{t("integrations-title")}</Title>
            <Text size="sm" c="dimmed">
              {t("integrations-description")}
            </Text>
          </Stack>

          <Card withBorder padding="lg" radius="md">
            <Stack gap="md">
              <Group gap="sm">
                <IconBrandGoogleDrive size={28} />
                <Stack gap={0}>
                  <Text fw={600}>{t("integrations-google-drive")}</Text>
                  <Text size="sm" c="dimmed">
                    {t("integrations-google-drive-desc")}
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
                onClick={handleConnect}
                loading={connecting || loading}
                disabled={ownerScope === "organization" && !hasOrganization}
              >
                {t("integrations-connect")}
              </Button>

              <Stack gap="sm">
                {renderOwnerStatus("user", t("integrations-owner-me"))}
                {hasOrganization &&
                  renderOwnerStatus(
                    "organization",
                    `${t("integrations-owner-organization")}${organizationName ? `: ${organizationName}` : ""}`
                  )}
              </Stack>
            </Stack>
          </Card>
        </Stack>
      </div>
    </main>
  );
}
