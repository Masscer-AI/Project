import { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  ActionIcon,
  Badge,
  FileInput,
  Group,
  Stack,
  Text,
  Title,
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
      <Stack gap="xs" mt="lg">
        <Title order={5}>{t("compliance-doc-section")}</Title>
        <Text size="sm" c="dimmed">
          {t("compliance-doc-locked")}
        </Text>
      </Stack>
    );
  }

  return (
    <Stack gap="sm" mt="lg">
      <Title order={5}>{t("compliance-doc-section")}</Title>
      <Text size="sm" c="dimmed">
        {t("compliance-doc-description")}
      </Text>
      {required.length > 0 && (
        <Text size="sm">
          {t("compliance-doc-progress", {
            uploaded: String(uploadedRequired),
            total: String(required.length),
          })}
        </Text>
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
  );
}
