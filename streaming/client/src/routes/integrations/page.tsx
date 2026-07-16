import React, { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Box,
  Stack,
  Tabs,
  Text,
  Title,
} from "@mantine/core";
import {
  IconBrandGoogleDrive,
  IconMenu2,
  IconPlug,
} from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { getUser } from "../../modules/apiCalls";
import { DriveIntegrationCard } from "./DriveIntegrationCard";
import { McpCredentialsSection } from "./McpCredentialsSection";
import { McpServerUrlCard } from "./McpServerUrlCard";
import { OAuthClientsSection } from "./OAuthClientsSection";

type IntegrationsTab = "drive" | "mcp";

function parseIntegrationsTab(raw: string | null): IntegrationsTab {
  return raw === "mcp" ? "mcp" : "drive";
}

export default function IntegrationsPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { chatState, toggleSidebar, user, setUser } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
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

        <Stack maw="52rem" w="100%" gap="lg" mt={48}>
          <Stack gap={4}>
            <Title order={2}>{t("integrations-title")}</Title>
            <Text size="sm" c="dimmed">
              {t("integrations-hub-description")}
            </Text>
          </Stack>

          <Tabs value={activeTab} onChange={setActiveTab} variant="outline">
            <Tabs.List mb="md">
              <Tabs.Tab
                value="drive"
                leftSection={<IconBrandGoogleDrive size={16} />}
              >
                {t("integrations-tab-drive")}
              </Tabs.Tab>
              <Tabs.Tab value="mcp" leftSection={<IconPlug size={16} />}>
                {t("integrations-tab-mcp")}
              </Tabs.Tab>
            </Tabs.List>

            <Tabs.Panel value="drive">
              <DriveIntegrationCard />
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
      </div>
    </main>
  );
}
