import React from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Box, Stack, Text, Title } from "@mantine/core";
import { IconMenu2 } from "@tabler/icons-react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";

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
        <Box px="md" w="100%" maw="32rem" mx="auto">
          <Stack align="center" gap="sm" mt="xl" pt="xl">
            <Title order={2} ta="center">
              {t("no-role-page-title")}
            </Title>
            <Text ta="center" c="dimmed" size="sm">
              {t("no-role-page-description")}
            </Text>
          </Stack>
        </Box>
      </div>
    </main>
  );
}
