import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { Alert, Badge, Button, Group, List, Stack, Text, Title } from "@mantine/core";
import { IconLoader2 } from "@tabler/icons-react";
import {
  confirmMyPldDocuments,
  listMyPldExpedients,
  TMyPldExpedient,
  TPldDocumentSlot,
} from "../../../modules/apiCalls";
import { PldClarificationRequests } from "./PldClarificationRequests";

function text(value: unknown): string {
  if (typeof value === "string" && value.trim()) return value.trim();
  return "";
}

function addressLine(value: unknown): string {
  if (!value || typeof value !== "object") return "";
  const row = value as Record<string, unknown>;
  return [
    row.street,
    row.exterior_number,
    row.neighborhood,
    row.city,
    row.state,
    row.postal_code,
    row.country,
  ]
    .map(text)
    .filter(Boolean)
    .join(", ");
}

function controllerNames(metadata: Record<string, unknown>): string[] {
  const names: string[] = [];
  const list = metadata.controllers;
  if (Array.isArray(list)) {
    for (const item of list) {
      if (item && typeof item === "object") {
        const name = text((item as Record<string, unknown>).name);
        if (name) names.push(name);
      }
    }
  }
  const single = metadata.controller;
  if (names.length === 0 && single && typeof single === "object") {
    const name = text((single as Record<string, unknown>).name);
    if (name) names.push(name);
  }
  if (metadata.is_own_controller === true) {
    const selfName =
      text(metadata.name) ||
      [text(metadata.given_names), text(metadata.surnames)].filter(Boolean).join(" ");
    if (selfName && names.length === 0) names.push(selfName);
  }
  return names;
}

function slotKindLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  slot: TPldDocumentSlot
) {
  return t(`compliance-doc-slot-${slot.document_kind}`, {
    name: slot.label_name || "",
    defaultValue: slot.document_kind,
  });
}

export function PldIdentificationDossier({
  row,
  onSaved,
  onBack,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
  onBack?: () => void;
}) {
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const metadata = row.metadata || {};
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
  const poll = pending || prequalPending || screeningPending || clarifyExtracting;
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
  const alreadyCross = row.expedient?.status === "cross_reference";
  const displayName =
    text(metadata.legal_name) ||
    text(metadata.name) ||
    [text(metadata.given_names), text(metadata.surnames)].filter(Boolean).join(" ") ||
    row.name;
  const identification = metadata.identification as Record<string, unknown> | undefined;
  const controllers = controllerNames(metadata);

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

  return (
    <Stack gap="md" mt="md">
      <Title order={4}>{t("compliance-dossier-title")}</Title>
      <Text size="sm">{t("compliance-dossier-intro")}</Text>
      {pending && !failed && (
        <Alert color="violet" variant="light">
          <Group gap="xs">
            <IconLoader2 size={16} />
            <Text size="sm">{t("compliance-dossier-extracting")}</Text>
          </Group>
        </Alert>
      )}
      {failed && (
        <Alert color="red" variant="light">
          {t("compliance-dossier-failed")}
        </Alert>
      )}
      {prequalPending && ready && (
        <Alert color="violet" variant="light">
          <Group gap="xs">
            <IconLoader2 size={16} />
            <Text size="sm">{t("compliance-prequal-running")}</Text>
          </Group>
        </Alert>
      )}
      {row.expedient?.prequalification_status === "failed" && (
        <Alert color="red" variant="light">
          {t("compliance-prequal-failed")}
        </Alert>
      )}
      {prequal?.summary && row.expedient?.prequalification_status === "succeeded" && (
        <Alert
          color={verdict === "ready_for_list_screening" ? "teal" : "yellow"}
          variant="light"
        >
          {prequal.summary}
        </Alert>
      )}
      {row.expedient?.screening_status === "pending" && (
        <Alert color="violet" variant="light">
          <Group gap="xs">
            <IconLoader2 size={16} />
            <Text size="sm">{t("compliance-screening-running")}</Text>
          </Group>
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
      <Stack gap={4}>
        <Text size="sm" fw={600}>
          {t("compliance-dossier-identity")}
        </Text>
        <Text size="sm">{displayName}</Text>
        {text(metadata.rfc) ? (
          <Text size="sm" c="dimmed">
            RFC: {text(metadata.rfc)}
          </Text>
        ) : null}
        {addressLine(metadata.address) ? (
          <Text size="sm" c="dimmed">
            {t("compliance-intake-address")}: {addressLine(metadata.address)}
          </Text>
        ) : null}
        {identification && (text(identification.document_type) || text(identification.document_number)) ? (
          <Text size="sm" c="dimmed">
            {t("compliance-intake-identification")}:{" "}
            {[text(identification.document_type), text(identification.document_number)]
              .filter(Boolean)
              .join(" · ")}
          </Text>
        ) : null}
      </Stack>
      <Stack gap={4}>
        <Text size="sm" fw={600}>
          {t("compliance-intake-controller")}
        </Text>
        {controllers.length === 0 ? (
          <Text size="sm" c="dimmed">
            {t("compliance-dossier-controller-empty")}
          </Text>
        ) : (
          <List size="sm" spacing={4}>
            {controllers.map((name) => (
              <List.Item key={name}>{name}</List.Item>
            ))}
          </List>
        )}
      </Stack>
      <Stack gap={6}>
        <Text size="sm" fw={600}>
          {t("compliance-doc-section")}
        </Text>
        {required.map((slot) => (
          <Group key={slot.slot_key} justify="space-between" gap="xs" wrap="nowrap">
            <Text size="sm">{slotKindLabel(t, slot)}</Text>
            <Badge
              size="xs"
              variant="light"
              color={
                slot.document?.extraction_status === "succeeded"
                  ? "teal"
                  : slot.document?.extraction_status === "failed"
                    ? "red"
                    : "violet"
              }
            >
              {slot.document?.extraction_status === "succeeded"
                ? t("compliance-dossier-extracted")
                : slot.document?.extraction_status === "failed"
                  ? t("compliance-dossier-extract-failed")
                  : t("compliance-dossier-extract-pending")}
            </Badge>
          </Group>
        ))}
      </Stack>
      {alreadyCross && openRequests.length === 0 ? (
        <Alert color="gray" variant="light">
          {t("compliance-dossier-next-lists")}
        </Alert>
      ) : alreadyCross ? null : (
        <Group>
          {onBack ? (
            <Button variant="default" onClick={onBack}>
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
        </Group>
      )}
    </Stack>
  );
}
