import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { OpenSidebarButton } from "../../../components/OpenSidebarButton/OpenSidebarButton";
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconMenu2 } from "@tabler/icons-react";
import { Sidebar } from "../../../components/Sidebar/Sidebar";
import { useStore } from "../../../modules/store";
import {
  listMyPldExpedients,
  resetMyPldExpedient,
  TMyPldExpedient,
} from "../../../modules/apiCalls";
import { PldDocumentCollection } from "./PldDocumentCollection";
import { PldIdentificationDossier } from "./PldIdentificationDossier";
import { PldIntakeForm } from "./PldIntakeForm";

const DOSSIER_LOCKED_STATUSES = new Set([
  "waiting_sign",
  "signed",
  "delivered",
]);

const DOSSIER_DEFAULT_STATUSES = new Set([
  "action_required",
  "cross_reference",
  "waiting_sign",
  "signed",
  "delivered",
]);

function shouldStartOnDossier(row: TMyPldExpedient): boolean {
  const status = row.expedient?.status;
  if (status && DOSSIER_DEFAULT_STATUSES.has(status)) return true;
  return (row.clarification_requests || []).some((item) => item.status === "open");
}

function ResetExpedienteButton({
  entityId,
  onReset,
}: {
  entityId: string;
  onReset: (next: TMyPldExpedient) => void;
}) {
  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);
  const [saving, setSaving] = useState(false);

  const handleConfirm = async () => {
    setSaving(true);
    try {
      const next = await resetMyPldExpedient(entityId);
      onReset(next);
      toast.success(t("compliance-expediente-reset-done"));
      close();
    } catch {
      toast.error(t("compliance-expediente-reset-error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Button variant="default" size="xs" onClick={open}>
        {t("compliance-expediente-reset")}
      </Button>
      <Modal
        opened={opened}
        onClose={close}
        title={t("compliance-expediente-reset-title")}
      >
        <Text size="sm" mb="md">
          {t("compliance-expediente-reset-body")}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={close}>
            {t("cancel")}
          </Button>
          <Button color="red" loading={saving} onClick={handleConfirm}>
            {t("compliance-expediente-reset-confirm")}
          </Button>
        </Group>
      </Modal>
    </>
  );
}

export default function MyPldExpedientePage() {
  const { t } = useTranslation();
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));
  const [rows, setRows] = useState<TMyPldExpedient[]>([]);
  const [loading, setLoading] = useState(true);
  const [reviewingIds, setReviewingIds] = useState<Record<string, boolean>>({});

  useEffect(() => {
    listMyPldExpedients()
      .then((data) => setRows(data.results || []))
      .catch(() => {
        toast.error(t("compliance-entities-load-error"));
        setRows([]);
      })
      .finally(() => setLoading(false));
  }, [t]);

  useEffect(() => {
    if (loading) return;
    setReviewingIds((prev) => {
      let changed = false;
      const next = { ...prev };
      for (const row of rows) {
        if (row.id in next) continue;
        if (shouldStartOnDossier(row)) {
          next[row.id] = true;
          changed = true;
        }
      }
      return changed ? next : prev;
    });
  }, [loading, rows]);

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
        <OpenSidebarButton />
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
                    <Group gap="xs">
                      {row.expedient && (
                        <Badge variant="light" color="violet">
                          {t(`compliance-status-${row.expedient.status}`, {
                            defaultValue: row.expedient.status,
                          })}
                        </Badge>
                      )}
                      {row.expedient && (
                        <ResetExpedienteButton
                          entityId={row.id}
                          onReset={(next) => {
                            setRows((prev) =>
                              prev.map((item) =>
                                item.id === next.id ? next : item
                              )
                            );
                            setReviewingIds((prev) => ({
                              ...prev,
                              [next.id]: false,
                            }));
                          }}
                        />
                      )}
                    </Group>
                  </Group>
                  {reviewingIds[row.id] ||
                  DOSSIER_LOCKED_STATUSES.has(row.expedient?.status || "") ? (
                    <PldIdentificationDossier
                      row={row}
                      onSaved={(next) =>
                        setRows((prev) =>
                          prev.map((item) => (item.id === next.id ? next : item))
                        )
                      }
                      onBack={
                        DOSSIER_LOCKED_STATUSES.has(row.expedient?.status || "")
                          ? undefined
                          : () =>
                              setReviewingIds((prev) => ({
                                ...prev,
                                [row.id]: false,
                              }))
                      }
                    />
                  ) : (
                    <>
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
                        onContinue={() =>
                          setReviewingIds((prev) => ({ ...prev, [row.id]: true }))
                        }
                      />
                    </>
                  )}
                </Card>
              ))}
            </Stack>
          )}
        </Box>
      </div>
    </main>
  );
}
