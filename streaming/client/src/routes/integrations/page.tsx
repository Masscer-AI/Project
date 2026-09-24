import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { AppPage } from "../../components/AppPage/AppPage";
import { Stack, Tabs, Text } from "@mantine/core";
import {
  IconBrandGoogleDrive,
  IconCalendar,
  IconPlug,
} from "@tabler/icons-react";
import { useStore } from "../../modules/store";
import { getUser } from "../../modules/apiCalls";
import { CalendarIntegrationCard } from "./CalendarIntegrationCard";
import { DriveIntegrationCard } from "./DriveIntegrationCard";
import { McpCredentialsSection } from "./McpCredentialsSection";
import { McpServerUrlCard } from "./McpServerUrlCard";
import { OAuthClientsSection } from "./OAuthClientsSection";

type IntegrationsTab = "drive" | "calendar" | "mcp";

function parseIntegrationsTab(raw: string | null): IntegrationsTab {
  if (raw === "mcp") return "mcp";
  if (raw === "calendar") return "calendar";
  return "drive";
}

export default function IntegrationsPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { user, setUser } = useStore((s) => ({
    user: s.user,
    setUser: s.setUser,
  }));

  const activeTab = parseIntegrationsTab(searchParams.get("tab"));
  const [credentialsRefreshKey, setCredentialsRefreshKey] = useState(0);

  useEffect(() => {
    if (!user) {
      getUser().then((data) => setUser(data)).catch(() => undefined);
    }
  }, [user, setUser]);

  useEffect(() => {
    const error = searchParams.get("error");
    if (error) {
      toast.error(t("integrations-connect-error"));
      searchParams.delete("error");
      setSearchParams(searchParams, { replace: true });
    }
  }, [searchParams, setSearchParams, t]);

  const setActiveTab = (value: string | null) => {
    if (!value) return;
    const next = new URLSearchParams(searchParams);
    if (value === "drive") {
      next.delete("tab");
    } else {
      next.set("tab", value);
    }
    setSearchParams(next, { replace: true });
  };

  return (
    <AppPage title={t("integrations-title")}>
        <Stack maw="52rem" w="100%" gap="lg">
          <Stack gap={4}>
            <Text size="sm" c="dimmed">
              {t("integrations-hub-description")}
            </Text>
          </Stack>

          <Tabs value={activeTab} onChange={setActiveTab}>
            <Tabs.List mb="md">
              <Tabs.Tab
                value="drive"
                leftSection={<IconBrandGoogleDrive size={16} />}
              >
                {t("integrations-tab-drive")}
              </Tabs.Tab>
              <Tabs.Tab
                value="calendar"
                leftSection={<IconCalendar size={16} />}
              >
                {t("integrations-tab-calendar")}
              </Tabs.Tab>
              <Tabs.Tab value="mcp" leftSection={<IconPlug size={16} />}>
                {t("integrations-tab-mcp")}
              </Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="drive">
              <DriveIntegrationCard />
            </Tabs.Panel>

            <Tabs.Panel value="calendar">
              <CalendarIntegrationCard />
            </Tabs.Panel>

            <Tabs.Panel value="mcp">
              <Stack gap="lg">
                <McpServerUrlCard />
                <McpCredentialsSection key={credentialsRefreshKey} />
                <OAuthClientsSection
                  onManualCredentialCreated={() =>
                    setCredentialsRefreshKey((k) => k + 1)
                  }
                />
              </Stack>
            </Tabs.Panel>
          </Tabs>
        </Stack>
    </AppPage>
  );
}
