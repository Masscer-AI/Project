import React, { useEffect } from "react";
import { useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Box,
  Divider,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconMenu2 } from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { getUser } from "../../modules/apiCalls";
import { DriveIntegrationCard } from "./DriveIntegrationCard";
import { McpCredentialsSection } from "./McpCredentialsSection";

export default function IntegrationsPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const { chatState, toggleSidebar, user, setUser } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
    user: s.user,
    setUser: s.setUser,
  }));

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

          <DriveIntegrationCard />

          <Divider />

          <McpCredentialsSection />
        </Stack>
      </div>
    </main>
  );
};
