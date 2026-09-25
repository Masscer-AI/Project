import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { AppPage } from "../../../components/AppPage/AppPage";
import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  Group,
  Loader,
  Menu,
  Modal,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconDots } from "@tabler/icons-react";
import { useDisclosure } from "@mantine/hooks";
import {
  listMyPldExpedients,
  resetMyPldExpedient,
  TMyPldExpedient,
} from "../../../modules/apiCalls";
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
  menu,
}: {
  entityId: string;
  onReset: (next: TMyPldExpedient) => void;
  menu?: boolean;
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
      {menu ? (
        <Menu position="bottom-end">
          <Menu.Target>
            <ActionIcon
              variant="default"
              size="lg"
              aria-label={t("compliance-expediente-reset")}
            >
              <IconDots size={18} />
            </ActionIcon>
          </Menu.Target>
          <Menu.Dropdown>
            <Menu.Item onClick={open}>{t("compliance-expediente-reset")}</Menu.Item>
          </Menu.Dropdown>
        </Menu>
      ) : (
        <Button variant="default" size="xs" onClick={open}>
          {t("compliance-expediente-reset")}
        </Button>
      )}
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
    <AppPage title={t("compliance-my-expediente-title")}>
        <Box px="md" w="100%" maw="72rem" mx="auto">
          <Text ta="center" c="dimmed" mb="lg" size="sm" mt="md">
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
              {rows.map((row) => {
                const leftSteps = reviewingIds[row.id] === false;
                const onDossier =
                  !leftSteps &&
                  (reviewingIds[row.id] ||
                    DOSSIER_LOCKED_STATUSES.has(row.expedient?.status || ""));
                const signStep = ["waiting_sign", "signed", "delivered"].includes(
                  row.expedient?.status || ""
                );
                const reset = row.expedient ? (
                  <ResetExpedienteButton
                    menu={signStep}
                    entityId={row.id}
                    onReset={(next) => {
                      setRows((prev) =>
                        prev.map((item) => (item.id === next.id ? next : item))
                      );
                      setReviewingIds((prev) => ({
                        ...prev,
                        [next.id]: false,
                      }));
                    }}
                  />
                ) : null;
                if (!onDossier) {
                  return (
                    <PldIntakeForm
                      key={row.id}
                      row={row}
                      headerExtra={reset}
                      onSaved={(next) =>
                        setRows((prev) =>
                          prev.map((item) => (item.id === next.id ? next : item))
                        )
                      }
                      onContinue={() =>
                        setReviewingIds((prev) => ({
                          ...prev,
                          [row.id]: true,
                        }))
                      }
                    />
                  );
                }
                if (signStep) {
                  return (
                    <Box key={row.id}>
                      <PldIdentificationDossier
                        row={row}
                        headerExtra={reset}
                        onBack={() =>
                          setReviewingIds((prev) => ({
                            ...prev,
                            [row.id]: false,
                          }))
                        }
                        onSaved={(next) =>
                          setRows((prev) =>
                            prev.map((item) => (item.id === next.id ? next : item))
                          )
                        }
                      />
                    </Box>
                  );
                }
                return (
                <Card key={row.id} withBorder p="md">
                  <Stack gap="sm">
                    <Stack gap={2}>
                      <Text fw={500}>{row.name}</Text>
                      <Text size="sm" c="dimmed">
                        {row.organization_name}
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
                      {reset}
                    </Group>
                  </Stack>
                  {onDossier ? (
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
                  ) : null}
                </Card>
                );
              })}
            </Stack>
          )}
        </Box>
    </AppPage>
  );
}
