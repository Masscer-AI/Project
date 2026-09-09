import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Accordion,
  ActionIcon,
  Alert,
  Badge,
  Button,
  FileInput,
  Group,
  Loader,
  Stack,
  Text,
} from "@mantine/core";
import { IconTrash, IconUpload } from "@tabler/icons-react";
import {
  deleteMyPldExpedientDocument,
  listMyPldExpedients,
  TMyPldExpedient,
  TPldDocumentSlot,
  uploadMyPldExpedientDocument,
} from "../../../modules/apiCalls";
import {
  extractionLines,
  PldExtractionDebugModal,
} from "./PldExtractionDebugModal";

const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp,application/xml,text/xml,application/zip,.pdf,.jpg,.jpeg,.png,.webp,.xml,.zip";

function requiredSlotsReady(row: TMyPldExpedient): boolean {
  const required = (row.document_slots || []).filter((slot) => slot.required);
  return (
    required.length > 0 &&
    required.every((slot) => slot.document?.extraction_status === "succeeded")
  );
}

function slotStatusColor(slot: TPldDocumentSlot): string {
  const status = slot.document?.extraction_status;
  if (status === "succeeded") return "teal";
  if (status === "failed") return "red";
  if (slot.document) return "violet";
  return slot.required ? "violet" : "gray";
}

function slotIsExtracting(slot: TPldDocumentSlot): boolean {
  const status = slot.document?.extraction_status;
  return Boolean(slot.document) && status !== "succeeded" && status !== "failed";
}

function slotStatusLabel(
  t: (key: string) => string,
  slot: TPldDocumentSlot
): string {
  const status = slot.document?.extraction_status;
  if (status === "succeeded") return t("compliance-dossier-extracted");
  if (status === "failed") return t("compliance-dossier-extract-failed");
  if (status === "pending" || slot.document) {
    return t("compliance-dossier-extract-pending");
  }
  return slot.required
    ? t("compliance-doc-required")
    : t("compliance-doc-optional");
}

function slotLabel(
  t: (key: string, options?: Record<string, unknown>) => string,
  slot: TPldDocumentSlot
) {
  return t(`compliance-doc-slot-${slot.document_kind}`, {
    name: slot.label_name || "",
    defaultValue: slot.document_kind,
  });
}

export function PldDocumentCollection({
  row,
  onSaved,
  onContinue,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
  onContinue: () => void;
}) {
  const { t } = useTranslation();
  const [busySlot, setBusySlot] = useState<string | null>(null);
  const [inspectSlot, setInspectSlot] = useState<TPldDocumentSlot | null>(null);
  const slots = row.document_slots || [];
  const required = slots.filter((slot) => slot.required);
  const uploadedRequired = required.filter((slot) => slot.document).length;
  const requiredFailed = required.some(
    (slot) => slot.document?.extraction_status === "failed"
  );
  const requiredPending = required.some(
    (slot) =>
      Boolean(slot.document) &&
      slot.document?.extraction_status !== "succeeded" &&
      slot.document?.extraction_status !== "failed"
  );
  const canContinue = requiredSlotsReady(row);
  const documentsUnlocked =
    row.expedient?.status && row.expedient.status !== "data_collection";
  const onSavedRef = useRef(onSaved);
  onSavedRef.current = onSaved;
  const hasPendingExtraction = slots.some(
    (slot) => slot.document?.extraction_status === "pending"
  );

  useEffect(() => {
    if (!hasPendingExtraction) return;
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
  }, [hasPendingExtraction, row.id]);

  const handleUpload = async (slot: TPldDocumentSlot, file: File | null) => {
    if (!file) return;
    setBusySlot(slot.slot_key);
    try {
      const saved = await uploadMyPldExpedientDocument(
        row.id,
        slot.slot_key,
        file
      );
      onSaved(saved);
      toast.success(t("compliance-doc-uploaded"));
    } catch {
      toast.error(t("compliance-doc-upload-error"));
    } finally {
      setBusySlot(null);
    }
  };

  const handleDelete = async (slot: TPldDocumentSlot) => {
    if (!slot.document) return;
    setBusySlot(slot.slot_key);
    try {
      const saved = await deleteMyPldExpedientDocument(row.id, slot.document.id);
      onSaved(saved);
      toast.success(t("compliance-doc-removed"));
    } catch {
      toast.error(t("compliance-doc-remove-error"));
    } finally {
      setBusySlot(null);
    }
  };

  if (!documentsUnlocked) {
    return (
      <Accordion variant="separated" radius="md" mt="md">
        <Accordion.Item value="documents">
          <Accordion.Control>
            <Group gap="xs" wrap="nowrap" justify="space-between" pr="sm">
              <Text fw={500}>{t("compliance-doc-section")}</Text>
              <Badge size="xs" variant="light" color="gray">
                {t("compliance-intake-section-pending")}
              </Badge>
            </Group>
          </Accordion.Control>
          <Accordion.Panel>
            <Text size="sm" c="dimmed">
              {t("compliance-doc-locked")}
            </Text>
          </Accordion.Panel>
        </Accordion.Item>
      </Accordion>
    );
  }

  return (
    <Accordion variant="separated" radius="md" mt="md" defaultValue="documents">
      <Accordion.Item value="documents">
        <Accordion.Control>
          <Group gap="xs" wrap="nowrap" justify="space-between" pr="sm">
            <Text fw={500}>{t("compliance-doc-section")}</Text>
            <Badge
              size="xs"
              variant="light"
              color={
                canContinue ? "teal" : requiredFailed ? "red" : "violet"
              }
            >
              {required.length > 0
                ? t("compliance-doc-progress", {
                    uploaded: String(uploadedRequired),
                    total: String(required.length),
                  })
                : t("compliance-intake-section-pending")}
            </Badge>
          </Group>
        </Accordion.Control>
        <Accordion.Panel>
          <Stack gap="sm">
      <Text size="sm" c="dimmed">
        {t("compliance-doc-description")}
      </Text>
      {requiredPending && !requiredFailed && (
        <Alert
          color="violet"
          variant="light"
          icon={<Loader size={16} type="oval" color="currentColor" />}
        >
          {t("compliance-doc-wait-extract")}
        </Alert>
      )}
      {requiredFailed && (
        <Alert color="red" variant="light">
          {t("compliance-doc-extract-blocked")}
        </Alert>
      )}
      {slots.map((slot) => (
        <Stack key={slot.slot_key} gap={6}>
          <Group justify="space-between" gap="xs" wrap="nowrap">
            <Text size="sm" fw={500}>
              {slotLabel(t, slot)}
            </Text>
            <Badge
              size="xs"
              variant="light"
              color={slotStatusColor(slot)}
              style={
                slot.document?.extraction_status === "succeeded"
                  ? { cursor: "pointer" }
                  : undefined
              }
              leftSection={
                slotIsExtracting(slot) ? (
                  <Loader size={10} color="violet" type="oval" />
                ) : undefined
              }
              onClick={() => {
                if (slot.document?.extraction_status === "succeeded") {
                  setInspectSlot(slot);
                }
              }}
            >
              {slotStatusLabel(t, slot)}
            </Badge>
          </Group>
          {slot.document ? (
            <Stack gap={6}>
              <Group gap="xs" wrap="nowrap">
                <Text size="sm" c="dimmed" style={{ flex: 1 }} truncate>
                  {slot.document.original_filename}
                </Text>
                <ActionIcon
                  variant="subtle"
                  color="gray"
                  size="sm"
                  aria-label={t("compliance-doc-remove")}
                  loading={busySlot === slot.slot_key}
                  onClick={() => handleDelete(slot)}
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
              {slot.document.extraction_status === "failed" && (
                <Text size="xs" c="red">
                  {t(
                    `compliance-doc-error-${slot.document.extraction_error || "extraction-failed"}`,
                    {
                      defaultValue: t("compliance-doc-error-extraction-failed"),
                    }
                  )}
                </Text>
              )}
              {slot.document.extraction_status === "succeeded" && (
                <Stack gap={2}>
                  {extractionLines(slot.document.extracted_payload).map((line) => (
                    <Text key={line.key} size="xs" c="dimmed">
                      <Text span fw={500}>
                        {t(`compliance-extract-${line.key}`, {
                          defaultValue: line.key.replace(/_/g, " "),
                        })}
                        {": "}
                      </Text>
                      {line.value}
                    </Text>
                  ))}
                </Stack>
              )}
            </Stack>
          ) : (
            <FileInput
              size="sm"
              accept={ACCEPT}
              placeholder={t("compliance-doc-choose")}
              leftSection={<IconUpload size={16} />}
              disabled={busySlot === slot.slot_key}
              value={null}
              onChange={(file) => handleUpload(slot, file)}
            />
          )}
        </Stack>
      ))}
      {uploadedRequired === required.length && required.length > 0 && (
        <Button
          color="violet"
          mt="sm"
          disabled={!canContinue}
          onClick={onContinue}
        >
          {t("compliance-doc-continue")}
        </Button>
      )}
      <PldExtractionDebugModal
        slot={inspectSlot}
        opened={Boolean(inspectSlot)}
        onClose={() => setInspectSlot(null)}
      />
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
