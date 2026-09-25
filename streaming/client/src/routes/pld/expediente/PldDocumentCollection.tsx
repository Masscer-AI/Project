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
  extractionSummary,
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

function ExtractionSummary({
  payload,
}: {
  payload: Record<string, unknown> | undefined;
}) {
  const summary = extractionSummary(payload);
  if (!summary) return null;
  return (
    <Text size="xs" c="dimmed">
      {summary}
    </Text>
  );
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
  if (slot.document_kind === "cfdi" && slot.label_name) {
    return t("compliance-doc-slot-cfdi-extra", { name: slot.label_name });
  }
  return t(`compliance-doc-slot-${slot.document_kind}`, {
    name: slot.label_name || "",
    defaultValue: slot.document_kind,
  });
}

const SECTION_KINDS: Record<string, string[]> = {
  entity: ["acta_constitutiva", "constancia_fiscal", "cfdi"],
  address: ["comprobante_domicilio"],
  representative: ["id_representante", "curp_representante", "poder"],
  identification: ["official_id", "curp", "acta_nacimiento"],
};

export function slotsForIntakeSection(
  section: string,
  slots: TPldDocumentSlot[],
  isMoral: boolean
): TPldDocumentSlot[] {
  if (section === "uploads") return slots;
  if (section === "controller") {
    return slots.filter(
      (slot) =>
        slot.document_kind === "id_controlador" ||
        slot.slot_key.startsWith("id_controlador")
    );
  }
  if (section === "entity" && !isMoral) {
    return slots.filter((slot) =>
      ["constancia_fiscal", "cfdi"].includes(slot.document_kind)
    );
  }
  if (section === "documents") {
    const placed = new Set(
      ["entity", "address", "representative", "identification", "controller"].flatMap(
        (id) => slotsForIntakeSection(id, slots, isMoral).map((slot) => slot.slot_key)
      )
    );
    return slots.filter((slot) => !placed.has(slot.slot_key));
  }
  const kinds = SECTION_KINDS[section] || [];
  return slots.filter((slot) => kinds.includes(slot.document_kind));
}

export function requiredSectionDocsReady(slots: TPldDocumentSlot[]): boolean {
  const required = slots.filter((slot) => slot.required);
  return required.every(
    (slot) => slot.document && slot.document.extraction_status !== "failed"
  );
}

export function requiredSectionDocsExtracted(slots: TPldDocumentSlot[]): boolean {
  const required = slots.filter((slot) => slot.required);
  return required.every(
    (slot) => slot.document?.extraction_status === "succeeded"
  );
}

export function PldDocumentCollection({
  row,
  onSaved,
  onContinue,
  embedded = false,
  section,
  isMoral = false,
  showContinue = false,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
  onContinue: () => void;
  embedded?: boolean;
  section?: string;
  isMoral?: boolean;
  showContinue?: boolean;
}) {
  const { t, i18n } = useTranslation();
  const [busySlot, setBusySlot] = useState<string | null>(null);
  const [inspectSlot, setInspectSlot] = useState<TPldDocumentSlot | null>(null);
  const allSlots = row.document_slots || [];
  const slots = section
    ? slotsForIntakeSection(section, allSlots, isMoral)
    : allSlots;
  const required = slots.filter((slot) => slot.required);
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
        file,
        i18n.language
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

  if (section && slots.length === 0) return null;

  const body = (
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
                <ExtractionSummary payload={slot.document.extracted_payload} />
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
      {showContinue && canContinue && (
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
  );

  if (embedded) return body;

  return (
    <Accordion variant="separated" radius="md" mt="md" defaultValue="documents">
      <Accordion.Item value="documents">
        <Accordion.Control>
          <Text fw={500}>{t("compliance-doc-section")}</Text>
        </Accordion.Control>
        <Accordion.Panel>{body}</Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
