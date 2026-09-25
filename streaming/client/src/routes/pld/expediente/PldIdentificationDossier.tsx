import { ReactNode, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { Alert, Badge, Button, Card, Group, Loader, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { IconAlertTriangle, IconCircleCheck, IconDownload, IconSignature } from "@tabler/icons-react";
import {
  confirmMyPldDocuments,
  downloadMyPldPacket,
  listMyPldExpedients,
  regenerateMyPldPacket,
  rerunMyPldPrequalification,
  TMyPldExpedient,
} from "../../../modules/apiCalls";
import { PldClarificationRequests } from "./PldClarificationRequests";
import { PldExpedientPreview } from "./PldExpedientPreview";
import { PldPrequalDebugModal } from "./PldPrequalDebugModal";

const MORAL_CHECKS = [
  { code: "rfc_mismatch", key: "compliance-sign-check-rfc" },
  { code: "legal_name_mismatch", key: "compliance-sign-check-name" },
  { code: "address_proof_stale", key: "compliance-sign-check-address" },
  { code: "id_expired_or_unreadable", key: "compliance-sign-check-representative" },
  { code: "controller_missing", key: "compliance-sign-check-controller" },
];

const FISICA_CHECKS = [
  { code: "rfc_mismatch", key: "compliance-sign-check-rfc" },
  { code: "curp_mismatch", key: "compliance-sign-check-curp" },
  { code: "legal_name_mismatch", key: "compliance-sign-check-name" },
  { code: "address_proof_stale", key: "compliance-sign-check-address" },
  { code: "id_expired_or_unreadable", key: "compliance-sign-check-id" },
];

export function PldIdentificationDossier({
  row,
  onSaved,
  onBack,
  headerExtra,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
  onBack?: () => void;
  headerExtra?: ReactNode;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const slots = row.document_slots || [];
  const required = slots.filter((slot) => slot.required);
  const pending = required.some(
    (slot) => !slot.document || slot.document.extraction_status === "pending"
  );
  const prequalPending = row.expedient?.prequalification_status === "pending";
  const screeningPending = row.expedient?.screening_status === "pending";
  const clarifyExtracting = (row.clarification_requests || []).some(
    (item) =>
      item.status === "open" && item.document?.extraction_status === "pending"
  );
  const status = row.expedient?.status || "";
  const waitingSign = status === "waiting_sign";
  const signedDone = status === "signed" || status === "delivered";
  const packetStatus = row.expedient?.packet_status || "";
  const packetWriting = packetStatus === "writing";
  const packetReady = packetStatus === "ready" || Boolean(row.expedient?.packet_ready);
  const poll =
    pending ||
    prequalPending ||
    screeningPending ||
    clarifyExtracting ||
    waitingSign ||
    packetWriting;
  const onSavedRef = useRef(onSaved);
  onSavedRef.current = onSaved;

  useEffect(() => {
    if (!poll) return;
    let cancelled = false;
    const refresh = async () => {
      try {
        const data = await listMyPldExpedients();
        const next = (data.results || []).find((item) => item.id === row.id);
        if (!cancelled && next) onSavedRef.current(next);
      } catch {
        return;
      }
    };
    const timer = window.setInterval(refresh, 2500);
    void refresh();
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [poll, row.id]);
  const failed = required.some(
    (slot) => slot.document?.extraction_status === "failed"
  );
  const ready =
    required.length > 0 &&
    required.every((slot) => slot.document?.extraction_status === "succeeded");
  const prequal = row.expedient?.prequalification;
  const verdict = prequal?.verdict;
  const openRequests = (row.clarification_requests || []).filter(
    (item) => item.status === "open"
  );
  const prequalReady =
    row.expedient?.prequalification_status === "succeeded" &&
    verdict === "ready_for_list_screening" &&
    openRequests.length === 0;
  const confirmEnabled = ready && prequalReady && !busy;
  const alreadyCross = status === "cross_reference";
  const hideConfirm = alreadyCross || waitingSign || signedDone;
  const canRerunPrequal =
    ready &&
    !prequalPending &&
    !waitingSign &&
    !signedDone &&
    (row.expedient?.prequalification_status === "succeeded" ||
      row.expedient?.prequalification_status === "failed");
  const handleConfirm = async () => {
    setBusy(true);
    try {
      const saved = await confirmMyPldDocuments(row.id);
      onSaved(saved);
      toast.success(t("compliance-dossier-confirmed"));
    } catch {
      toast.error(t("compliance-dossier-confirm-error"));
    } finally {
      setBusy(false);
    }
  };

  const handleRerunPrequal = async () => {
    setBusy(true);
    try {
      const saved = await rerunMyPldPrequalification(row.id);
      onSaved(saved);
      toast.success(t("compliance-prequal-rerun-done"));
    } catch {
      toast.error(t("compliance-prequal-rerun-error"));
    } finally {
      setBusy(false);
    }
  };

  const handleRegeneratePacket = async () => {
    setBusy(true);
    try {
      const saved = await regenerateMyPldPacket(row.id);
      onSaved(saved);
    } catch {
      toast.error(t("compliance-packet-regenerate-error"));
    } finally {
      setBusy(false);
    }
  };

  const handleDownloadPacket = async () => {
    setBusy(true);
    try {
      await downloadMyPldPacket(row.id);
    } catch {
      toast.error(t("compliance-sign-download-error"));
    } finally {
      setBusy(false);
    }
  };

  const signLayout = waitingSign || signedDone;
  const checks = row.person_type === "persona_moral" ? MORAL_CHECKS : FISICA_CHECKS;
  const findingByCode = new Map(
    (prequal?.debug?.findings || [])
      .filter((item) => item.code)
      .map((item) => [item.code as string, item.summary || ""])
  );
  const passedChecks = checks.filter((item) => !findingByCode.has(item.code));
  const signRejected =
    row.expedient?.signing?.status === "rejected" ||
    row.expedient?.signing?.status === "error";

  if (signLayout) {
    return (
      <Stack gap="lg" mt="md">
        {onBack ? (
          <Button variant="subtle" color="gray" w="fit-content" onClick={onBack}>
            {t("compliance-sign-back")}
          </Button>
        ) : null}
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Stack gap={6}>
            <Text size="sm" c="dimmed">
              {t("compliance-expediente-requested-by", {
                name: row.organization_name,
              })}
            </Text>
            <Title order={2}>{row.name}</Title>
            {status ? (
              <Badge variant="light" color="violet" w="fit-content">
                {t(`compliance-status-${status}`, { defaultValue: status })}
              </Badge>
            ) : null}
          </Stack>
          {headerExtra}
        </Group>
        <SimpleGrid cols={{ base: 1, md: 2 }} spacing="md">
          <Stack gap="sm">
            <Card withBorder radius="md" p="md">
              <Group gap="sm" wrap="nowrap" align="flex-start" mb="sm">
                {passedChecks.length === checks.length ? (
                  <IconCircleCheck size={22} color="var(--mantine-color-teal-5)" />
                ) : (
                  <IconAlertTriangle size={22} color="var(--mantine-color-yellow-5)" />
                )}
                <Stack gap={0}>
                  {passedChecks.length === checks.length ? (
                    <Text size="sm" fw={600}>
                      {t(
                        row.person_type === "persona_moral"
                          ? "compliance-sign-checks-ok-moral"
                          : "compliance-sign-checks-ok-fisica"
                      )}
                    </Text>
                  ) : null}
                  <Text size="xs" c="dimmed">
                    {t("compliance-sign-checks-count", {
                      done: passedChecks.length,
                      total: checks.length,
                    })}
                  </Text>
                </Stack>
              </Group>
              <Stack gap={0}>
                {checks.map((item) => {
                  const failed = findingByCode.get(item.code);
                  return (
                    <Group
                      key={item.code}
                      gap="sm"
                      wrap="nowrap"
                      align="flex-start"
                      py={8}
                      style={{ borderTop: "1px solid var(--mantine-color-dark-4)" }}
                    >
                      {failed ? (
                        <IconAlertTriangle size={16} color="var(--mantine-color-yellow-5)" />
                      ) : (
                        <IconCircleCheck size={16} color="var(--mantine-color-teal-5)" />
                      )}
                      <Text size="sm">{failed || t(item.key)}</Text>
                    </Group>
                  );
                })}
              </Stack>
            </Card>
            {row.expedient?.screening?.summary &&
            row.expedient.screening_status === "succeeded" ? (
              <Alert color="gray" variant="light">
                {row.expedient.screening.summary}
              </Alert>
            ) : null}
          </Stack>
          <Stack gap="sm">
            <Card withBorder radius="md" p="md">
              <Stack gap="sm">
                <Text fw={600}>{t("compliance-sign-title")}</Text>
                <Text size="sm" c="dimmed">
                  {signedDone ? t("compliance-sign-done") : t("compliance-sign-intro")}
                </Text>
                {signRejected ? (
                  <Alert color="yellow" variant="light" icon={<IconAlertTriangle size={16} />}>
                    {t("compliance-sign-rejected")}
                  </Alert>
                ) : null}
                {waitingSign && !row.expedient?.signing?.url ? (
                  <Group gap="xs">
                    <Loader size={16} type="oval" color="violet" />
                    <Text size="sm">{t("compliance-sign-preparing")}</Text>
                  </Group>
                ) : null}
                {waitingSign && row.expedient?.signing?.url ? (
                  <Button
                    component="a"
                    href={row.expedient.signing.url}
                    color="violet"
                    fullWidth
                    leftSection={<IconSignature size={16} />}
                  >
                    {t("compliance-sign-cta")}
                  </Button>
                ) : null}
                {packetWriting ? (
                  <Group gap="xs">
                    <Loader size={16} type="oval" color="violet" />
                    <Text size="sm">{t("compliance-packet-writing")}</Text>
                  </Group>
                ) : null}
                {packetStatus === "failed" ? (
                  <Alert color="red" variant="light">
                    {t("compliance-packet-failed")}
                  </Alert>
                ) : null}
                {packetReady ? (
                  <Button
                    type="button"
                    variant="default"
                    fullWidth
                    leftSection={<IconDownload size={16} />}
                    loading={busy}
                    onClick={handleDownloadPacket}
                  >
                    {t("compliance-sign-download")}
                  </Button>
                ) : null}
                <Button
                  type="button"
                  variant="subtle"
                  color="gray"
                  fullWidth
                  loading={busy || packetWriting}
                  disabled={packetWriting}
                  onClick={handleRegeneratePacket}
                >
                  {t("compliance-packet-regenerate")}
                </Button>
              </Stack>
            </Card>
            <PldExpedientPreview row={row} fullWidth />
          </Stack>
        </SimpleGrid>
        <PldClarificationRequests row={row} onSaved={onSaved} />
      </Stack>
    );
  }

  return (
    <Stack gap="md" mt="md">
      <Title order={4}>{t("compliance-dossier-title")}</Title>
      <Text size="sm">{t("compliance-dossier-intro")}</Text>
      {pending && !failed && (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-dossier-extracting")}
        </Alert>
      )}
      {failed && (
        <Alert color="red" variant="light">
          {t("compliance-dossier-failed")}
        </Alert>
      )}
      {prequalPending && ready && (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-prequal-running")}
        </Alert>
      )}
      {row.expedient?.prequalification_status === "failed" && (
        <Stack gap="sm">
          <Alert color="red" variant="light">
            {t("compliance-prequal-failed")}
          </Alert>
          {canRerunPrequal ? (
            <Button
              variant="default"
              size="xs"
              loading={busy}
              onClick={handleRerunPrequal}
              w="fit-content"
            >
              {t("compliance-prequal-rerun")}
            </Button>
          ) : null}
        </Stack>
      )}
      {prequal?.summary && row.expedient?.prequalification_status === "succeeded" && (
        <Stack gap="sm">
          <Alert
            color={verdict === "ready_for_list_screening" ? "teal" : "yellow"}
            variant="light"
          >
            {prequal.summary}
          </Alert>
          <Group gap="sm">
            <PldPrequalDebugModal row={row} />
            {canRerunPrequal ? (
              <Button
                variant="default"
                size="xs"
                loading={busy}
                onClick={handleRerunPrequal}
              >
                {t("compliance-prequal-rerun")}
              </Button>
            ) : null}
          </Group>
        </Stack>
      )}
      {row.expedient?.screening_status === "pending" && (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-screening-running")}
        </Alert>
      )}
      {row.expedient?.screening_status === "failed" && (
        <Alert color="red" variant="light">
          {t("compliance-screening-failed")}
        </Alert>
      )}
      {row.expedient?.screening?.summary &&
        row.expedient?.screening_status === "succeeded" && (
          <Alert color="gray" variant="light">
            {row.expedient.screening.summary}
          </Alert>
        )}
      <PldClarificationRequests row={row} onSaved={onSaved} />
      {alreadyCross && openRequests.length === 0 ? (
        <Alert color="gray" variant="light">
          {t("compliance-dossier-next-lists")}
        </Alert>
      ) : null}
      {packetWriting ? (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-packet-writing")}
        </Alert>
      ) : null}
      {packetStatus === "failed" ? (
        <Alert color="red" variant="light">
          {t("compliance-packet-failed")}
        </Alert>
      ) : null}
      <Group>
        <PldExpedientPreview row={row} />
        {hideConfirm ? null : (
          <>
            {onBack ? (
              <Button type="button" variant="default" onClick={onBack}>
                {t("compliance-dossier-back")}
              </Button>
            ) : null}
            <Button
              color="violet"
              disabled={!confirmEnabled}
              loading={busy}
              onClick={handleConfirm}
            >
              {t("compliance-dossier-confirm")}
            </Button>
          </>
        )}
      </Group>
    </Stack>
  );
}
