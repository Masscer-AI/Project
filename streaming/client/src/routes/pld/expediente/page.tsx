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
} from "@mantine/core";
import { IconDots, IconDownload, IconRefresh } from "@tabler/icons-react";
import { useDisclosure } from "@mantine/hooks";
import {
  downloadMyPldRunPacket,
  listMyPldExpedients,
  resetMyPldExpedient,
  startMyPldRun,
  TMyPldExpedient,
} from "../../../modules/apiCalls";
import { flowFurthest, PldIdentificationDossier, ProcessBar, stepLabelKeys } from "./PldIdentificationDossier";
import { PldIntakeForm } from "./PldIntakeForm";

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

function NewRunButton({
  entityId,
  onStarted,
}: {
  entityId: string;
  onStarted: (next: TMyPldExpedient) => void;
}) {
  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);
  const [saving, setSaving] = useState(false);

  const handleConfirm = async () => {
    setSaving(true);
    try {
      onStarted(await startMyPldRun(entityId));
      toast.success(t("compliance-new-run-started"));
      close();
    } catch {
      toast.error(t("compliance-new-run-error"));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      <Button size="xs" leftSection={<IconRefresh size={14} />} onClick={open}>
        {t("compliance-new-run")}
      </Button>
      <Modal opened={opened} onClose={close} title={t("compliance-new-run")}>
        <Text size="sm" mb="md">
          {t("compliance-new-run-hint-self")}
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={close}>
            {t("cancel")}
          </Button>
          <Button loading={saving} onClick={handleConfirm}>
            {t("compliance-new-run")}
          </Button>
        </Group>
      </Modal>
    </>
  );
}

function RunHistory({ row }: { row: TMyPldExpedient }) {
  const { t } = useTranslation();
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const past = (row.runs || []).slice(1);
  if (past.length === 0) return null;

  const download = async (runId: string, run: () => Promise<void>) => {
    setDownloadingId(runId);
    try {
      await run();
    } catch {
      toast.error(t("compliance-files-download-error"));
    } finally {
      setDownloadingId(null);
    }
  };

  return (
    <Card withBorder p="lg">
      <Text fw={500} mb="sm">
        {t("compliance-history-title")}
      </Text>
      <Stack gap="xs">
        {past.map((run) => (
          <Group key={run.id} justify="space-between" wrap="nowrap">
            <Stack gap={2}>
              <Group gap="xs">
                <Text size="sm" fw={500}>
                  {t("compliance-history-version", { version: run.version })}
                </Text>
                <Badge size="xs" variant="light" color="gray">
                  {t(`compliance-status-${run.status}`, { defaultValue: run.status })}
                </Badge>
              </Group>
              <Text size="xs" c="dimmed">
                {run.completed_at
                  ? t("compliance-history-completed", {
                      date: new Date(run.completed_at).toLocaleDateString(),
                    })
                  : t("compliance-history-started", {
                      date: new Date(run.created_at).toLocaleDateString(),
                    })}
              </Text>
            </Stack>
            {run.files.packet ? (
              <Button
                size="xs"
                variant="subtle"
                leftSection={<IconDownload size={14} />}
                loading={downloadingId === run.id}
                onClick={() =>
                  void download(run.id, () => downloadMyPldRunPacket(row.id, run))
                }
              >
                {t(`compliance-files-packet-${run.files.packet}`)}
              </Button>
            ) : null}
          </Group>
        ))}
      </Stack>
    </Card>
  );
}

export default function MyPldExpedientePage() {
  const { t } = useTranslation();
  const [rows, setRows] = useState<TMyPldExpedient[]>([]);
  const [loading, setLoading] = useState(true);
  const [flowStep, setFlowStep] = useState<Record<string, number>>({});

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
                const reached = Math.max(flowFurthest(row), flowStep[row.id] ?? 0);
                const view =
                  flowStep[row.id] != null
                    ? Math.min(flowStep[row.id], reached)
                    : flowFurthest(row);
                const signStep = ["waiting_sign", "signed", "delivered"].includes(
                  row.expedient?.status || ""
                );
                const pickStep = (step: number) =>
                  setFlowStep((prev) => ({ ...prev, [row.id]: step }));
                const saveRow = (next: TMyPldExpedient) =>
                  setRows((prev) => prev.map((item) => (item.id === next.id ? next : item)));
                const closed = ["signed", "delivered"].includes(
                  row.expedient?.status || ""
                );
                const reset = !row.expedient ? null : closed ? (
                  <NewRunButton
                    entityId={row.id}
                    onStarted={(next) => {
                      saveRow(next);
                      pickStep(0);
                    }}
                  />
                ) : (
                  <ResetExpedienteButton
                    menu={signStep}
                    entityId={row.id}
                    onReset={(next) => {
                      saveRow(next);
                      pickStep(0);
                    }}
                  />
                );
                const stepLabels = stepLabelKeys(row).map((key) => t(key));
                return (
                  <Stack key={row.id} gap="md">
                    <ProcessBar furthest={reached} current={view} labels={stepLabels} onPick={pickStep} />
                    {view === 0 ? (
                      <PldIntakeForm
                        row={row}
                        headerExtra={reset}
                        onSaved={saveRow}
                        onContinue={() => pickStep(1)}
                      />
                    ) : (
                      <PldIdentificationDossier
                        row={row}
                        headerExtra={reset}
                        showBar={false}
                        forcedView={view}
                        onNext={() => pickStep(Math.min(view + 1, stepLabels.length - 1))}
                        onSaved={saveRow}
                      />
                    )}
                    <RunHistory row={row} />
                  </Stack>
                );
              })}
            </Stack>
          )}
        </Box>
    </AppPage>
  );
}
