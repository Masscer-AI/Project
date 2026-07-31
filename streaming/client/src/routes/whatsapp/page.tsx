import React, { useEffect, useState } from "react";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import "./page.css";
import { getWhatsappNumbers } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";

import {
  ActionIcon,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconMenu2, IconMessages, IconPhone } from "@tabler/icons-react";
import type { WhatsappLine } from "./shared";

export default function Whatsapp() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const [numbers, setNumbers] = useState<WhatsappLine[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getWhatsappNumbers()
      .then((res) => {
        if (!cancelled) {
          setNumbers(res as WhatsappLine[]);
          setLoadError(null);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLoadError(t("whatsapp-load-error"));
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [t]);

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

        <Box px="md" w="100%" maw="42rem" mx="auto">
          <Title order={2} ta="center" mb="lg" mt="md">
            {t("whatsapp")}
          </Title>
          <Text mb="md">{t("whatsapp-intro")}</Text>
          <Text size="sm" c="dimmed" mb="md">
            {t("whatsapp-provision-note")}
          </Text>

          <Title order={4} mb="sm">
            {t("whatsapp-your-numbers")}
          </Title>

          {loading ? (
            <Stack align="center" py="xl">
              <Loader color="violet" />
            </Stack>
          ) : loadError ? (
            <Text c="red">{loadError}</Text>
          ) : numbers.length === 0 ? (
            <Text c="dimmed">{t("whatsapp-empty-lines")}</Text>
          ) : (
            <Stack gap="md">
              {numbers.map((line) => (
                <Card
                  key={line.id}
                  withBorder
                  padding="lg"
                  style={{ cursor: "pointer" }}
                  onClick={() => navigate(`/whatsapp/${line.id}`)}
                >
                  <Title order={4} ta="center">
                    {line.name || line.number}
                  </Title>
                  <Group justify="center" gap="xs" mt={4}>
                    <IconPhone size={16} />
                    <Text size="lg">{line.number}</Text>
                  </Group>
                  <Group justify="center" gap="md" mt="xs">
                    <Text size="sm">🧠 {line.agent.name}</Text>
                    <Text size="sm">💬 {line.conversations_count}</Text>
                  </Group>
                  <Group
                    justify="center"
                    mt="sm"
                    onClick={(e) => e.stopPropagation()}
                  >
                    <Button
                      size="xs"
                      variant="light"
                      leftSection={<IconMessages size={14} />}
                      onClick={() =>
                        navigate(
                          `/dashboard?wsNumberId=${line.id}&channel=whatsapp`
                        )
                      }
                    >
                      {t("view-conversations")}
                    </Button>
                  </Group>
                </Card>
              ))}
            </Stack>
          )}
        </Box>
      </div>
    </main>
  );
}
