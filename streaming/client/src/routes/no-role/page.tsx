import React from "react";
import { useTranslation } from "react-i18next";
import { Box, Stack, Text } from "@mantine/core";
import { IconMenu2 } from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { AppHeader } from "../../components/AppHeader/AppHeader";

export default function NoRolePage() {
  const { t } = useTranslation();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

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
          flexDirection: "column",
        }}
        className="relative"
      >
        <AppHeader title={t("no-role-page-title")} />
        <Box px="md" w="100%" maw="32rem" mx="auto">
          <Stack align="center" gap="sm" mt="xl" pt="xl">
            <Text ta="center" c="dimmed" size="sm">
              {t("no-role-page-description")}
            </Text>
          </Stack>
        </Box>
      </div>
    </main>
  );
}
