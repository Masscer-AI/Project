import React, { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { AppPage } from "../../../components/AppPage/AppPage";
import {
  ActionIcon,
  Box,
  Button,
  Group,
  Loader,
  Menu,
  Modal,
  Stack,
  Text,
} from "@mantine/core";
import { IconDots } from "@tabler/icons-react";
import { useDisclosure } from "@mantine/hooks";
import {
  listMyPldExpedients,
  resetMyPldExpedient,
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
                const reset = row.expedient ? (
                  <ResetExpedienteButton
                    menu={signStep}
                    entityId={row.id}
                    onReset={(next) => {
                      saveRow(next);
                      pickStep(0);
                    }}
                  />
                ) : null;
                const stepLabels = stepLabelKeys(row).map((key) => t(key));
                return (
                  <Stack key={row.id} gap="md">
                    {reached > 0 ? (
                      <ProcessBar furthest={reached} current={view} labels={stepLabels} onPick={pickStep} />
                    ) : null}
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
                  </Stack>
                );
              })}
            </Stack>
          )}
        </Box>
    </AppPage>
  );
}
