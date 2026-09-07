import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  Accordion,
  ActionIcon,
  Badge,
  FileInput,
  Group,
  Stack,
  Text,
} from "@mantine/core";
import { IconTrash, IconUpload } from "@tabler/icons-react";
import {
  deleteMyPldExpedientDocument,
  TMyPldExpedient,
  TPldDocumentSlot,
  uploadMyPldExpedientDocument,
} from "../../../modules/apiCalls";

const ACCEPT = "application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp";

function slotLabel(t: (key: string, options?: Record<string, unknown>) => string, slot: TPldDocumentSlot) {
  return t(`compliance-doc-slot-${slot.document_kind}`, {
    name: slot.label_name || "",
    defaultValue: slot.document_kind,
  });
}

export function PldDocumentCollection({
  row,
  onSaved,
}: {
  row: TMyPldExpedient;
  onSaved: (next: TMyPldExpedient) => void;
}) {
  const { t } = useTranslation();
  const [busySlot, setBusySlot] = useState<string | null>(null);
  const slots = row.document_slots || [];
  const required = slots.filter((slot) => slot.required);
  const uploadedRequired = required.filter((slot) => slot.document).length;
  const documentsUnlocked =
    row.expedient?.status && row.expedient.status !== "data_collection";

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
          </Stack>
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}
