import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Accordion,
  ActionIcon,
  Badge,
  Button,
  FileInput,
  Group,
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

const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp,application/xml,text/xml,application/zip,.pdf,.jpg,.jpeg,.png,.webp,.xml,.zip";

function asRecord(value: unknown): Record<string, unknown> | null {
  if (value && typeof value === "object" && !Array.isArray(value)) {
    return value as Record<string, unknown>;
  }
  return null;
}

function filledText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  if (typeof value === "boolean") return value ? "si" : "no";
  return null;
}

function formatAddress(value: unknown): string | null {
  const row = asRecord(value);
  if (!row) return filledText(value);
  const parts = [
    row.street,
    row.exterior_number,
    row.interior_number,
    row.neighborhood,
    row.municipality,
    row.city,
    row.state,
    row.postal_code,
    row.country,
    row.raw_text,
  ]
    .map(filledText)
    .filter((part): part is string => Boolean(part));
  return parts.length > 0 ? [...new Set(parts)].join(", ") : null;
}

function formatPeople(value: unknown): string | null {
  if (!Array.isArray(value) || value.length === 0) return null;
  const parts = value
    .map((item) => {
      const row = asRecord(item);
      if (!row) return filledText(item);
      const name =
        filledText(row.name) ||
        filledText(row.full_name) ||
        filledText(row.attorney_name) ||
        filledText(row.legal_name_or_full_name);
      const extra =
        filledText(row.ownership_percentage) ||
        filledText(row.role) ||
        filledText(row.rfc);
      if (name && extra) return `${name} (${extra})`;
      return name;
    })
    .filter((part): part is string => Boolean(part));
  return parts.length > 0 ? parts.join(" · ") : null;
}

function extractionLines(
  payload: Record<string, unknown> | undefined
): { key: string; value: string }[] {
  const row = payload || {};
  const skip = new Set([
    "name_matches_client_hint",
    "photo_present",
    "signature_present",
    "ownership_may_be_stale",
    "provenances",
    "_meta",
  ]);
  const lines: { key: string; value: string }[] = [];
  const push = (key: string, raw: unknown) => {
    if (skip.has(key) || raw == null || raw === "") return;
    if (key === "address" || key.endsWith("_address") || key === "tax_address" || key === "service_address" || key === "registered_address") {
      const formatted = formatAddress(raw);
      if (formatted) lines.push({ key, value: formatted });
      return;
    }
    if (key === "notary") {
      const formatted = formatAddress(raw) || formatPeople([raw]);
      const notary = asRecord(raw);
      const bits = notary
        ? [
            filledText(notary.name),
            filledText(notary.notaria_number),
            filledText(notary.escritura_number),
            filledText(notary.city),
          ].filter((part): part is string => Boolean(part))
        : [];
      if (bits.length > 0) lines.push({ key, value: bits.join(" · ") });
      else if (formatted) lines.push({ key, value: formatted });
      return;
    }
    if (Array.isArray(raw)) {
      if (raw.every((item) => typeof item === "string")) {
        const joined = raw.map(filledText).filter((part): part is string => Boolean(part));
        if (joined.length > 0) lines.push({ key, value: joined.join(" · ") });
        return;
      }
      const formatted = formatPeople(raw);
      if (formatted) lines.push({ key, value: formatted });
      return;
    }
    const text = filledText(raw);
    if (text) lines.push({ key, value: text });
  };
  Object.entries(row).forEach(([key, value]) => push(key, value));
  return lines;
}

function slotLabel(t: (key: string, options?: Record<string, unknown>) => string, slot: TPldDocumentSlot) {
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
  const slots = row.document_slots || [];
  const required = slots.filter((slot) => slot.required);
  const uploadedRequired = required.filter((slot) => slot.document).length;
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
              color={uploadedRequired === required.length && required.length > 0 ? "teal" : "violet"}
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
      {slots.map((slot) => (
        <Stack key={slot.slot_key} gap={6}>
          <Group justify="space-between" gap="xs" wrap="nowrap">
            <Text size="sm" fw={500}>
              {slotLabel(t, slot)}
            </Text>
            <Badge
              size="xs"
              variant="light"
              color={slot.document ? "green" : slot.required ? "violet" : "gray"}
            >
              {slot.document
                ? t("compliance-doc-uploaded-badge")
                : slot.required
                  ? t("compliance-doc-required")
                  : t("compliance-doc-optional")}
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
        <Button color="violet" mt="sm" onClick={onContinue}>
          {t("compliance-doc-continue")}
        </Button>
      )}
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
