import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  Box,
  Card,
  Group,
  Loader,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconMenu2 } from "@tabler/icons-react";
import { Sidebar } from "../../../components/Sidebar/Sidebar";
import { useStore } from "../../../modules/store";
import { listMyPldExpedients, TMyPldExpedient } from "../../../modules/apiCalls";
import { PldDocumentCollection } from "./PldDocumentCollection";
import { PldIntakeForm } from "./PldIntakeForm";

export default function MyPldExpedientePage() {
  const { t } = useTranslation();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));
  const [rows, setRows] = useState<TMyPldExpedient[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listMyPldExpedients()
      .then((data) => setRows(data.results || []))
      .catch(() => {
        toast.error(t("compliance-entities-load-error"));
        setRows([]);
      })
      .finally(() => setLoading(false));
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
        <Box px="md" w="100%" maw="52rem" mx="auto">
          <Title order={2} ta="center" mb="xs" mt="md">
            {t("compliance-my-expediente-title")}
          </Title>
          <Text ta="center" c="dimmed" mb="lg" size="sm">
            {t("compliance-my-expediente-description")}
          </Text>
          {loading ? (
            <Stack align="center" py="xl">
              <Loader color="violet" size="sm" />
            </Stack>
          ) : rows.length === 0 ? (
            <Text c="dimmed" ta="center" py="xl">
              {t("compliance-my-expediente-empty")}
            </Text>
          ) : (
            <Stack gap="md">
              {rows.map((row) => (
                <Card key={row.id} withBorder p="md">
                  <Group justify="space-between" align="flex-start">
                    <Stack gap={2}>
                      <Text fw={500}>{row.name}</Text>
                      <Text size="sm" c="dimmed">
                        {row.organization_name}
                      </Text>
                      <Text size="xs" c="dimmed">
                        {row.person_type === "persona_moral"
                          ? t("compliance-intake-moral-section")
                          : t("compliance-intake-fisica-section")}
                      </Text>
                    </Stack>
                    {row.expedient && (
                      <Badge variant="light" color="violet">
                        {t(`compliance-status-${row.expedient.status}`, {
                          defaultValue: row.expedient.status,
                        })}
                      </Badge>
                    )}
                  </Group>
                  <PldIntakeForm
                    row={row}
                    onSaved={(next) =>
                      setRows((prev) =>
                        prev.map((item) => (item.id === next.id ? next : item))
                      )
                    }
                  />
                  <PldDocumentCollection
                    row={row}
                    onSaved={(next) =>
                      setRows((prev) =>
                        prev.map((item) => (item.id === next.id ? next : item))
                      )
                    }
                  />
                </Card>
              ))}
            </Stack>
          )}
        </Box>
      </div>
    </main>
  );
}
