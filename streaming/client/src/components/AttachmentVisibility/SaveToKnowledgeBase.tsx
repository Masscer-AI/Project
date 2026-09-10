import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { ActionIcon, Button, Group, Modal, Stack, Text, Tooltip } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconBooks } from "@tabler/icons-react";
import { addAttachmentToKnowledgeBase } from "../../modules/apiCalls";

export function canSaveAttachmentToKnowledgeBase(
  type?: string,
  contentType?: string
): boolean {
  if (type === "video" || type === "audio") return false;
  const ct = (contentType || "").toLowerCase();
  if (ct.startsWith("video/") || ct.startsWith("audio/")) return false;
  if (type === "image" || type === "document") return true;
  if (ct.startsWith("image/")) return true;
  return Boolean(type || contentType);
}

function errorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error !== null &&
    "response" in error &&
    typeof (error as { response?: { data?: { error?: string } } }).response
      ?.data?.error === "string"
  ) {
    return (error as { response: { data: { error: string } } }).response.data
      .error;
  }
  return fallback;
}

export function SaveToKnowledgeBaseButton({
  attachmentId,
  type,
  contentType,
  variant = "button",
}: {
  attachmentId?: string;
  type?: string;
  contentType?: string;
  variant?: "button" | "icon";
}) {
  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);
  const [saving, setSaving] = useState(false);

  if (!canSaveAttachmentToKnowledgeBase(type, contentType)) {
    return null;
  }

  const handleSave = async () => {
    if (!attachmentId) return;
    setSaving(true);
    try {
      const result = await addAttachmentToKnowledgeBase(attachmentId);
      toast.success(
        result?.already_indexed
          ? t("save-to-knowledge-base-already")
          : t("save-to-knowledge-base-success")
      );
      close();
    } catch (error) {
      toast.error(errorMessage(error, t("save-to-knowledge-base-error")));
    } finally {
      setSaving(false);
    }
  };

  return (
    <>
      {variant === "icon" ? (
        <Tooltip label={t("save-to-knowledge-base")}>
          <ActionIcon
            variant="subtle"
            color="gray"
            size="sm"
            onClick={open}
            disabled={!attachmentId}
            aria-label={t("save-to-knowledge-base")}
          >
            <IconBooks size={16} />
          </ActionIcon>
        </Tooltip>
      ) : (
        <Button
          variant="default"
          leftSection={<IconBooks size={16} />}
          onClick={open}
          disabled={!attachmentId}
        >
          {t("save-to-knowledge-base")}
        </Button>
      )}
      <Modal
        opened={opened}
        onClose={close}
        title={t("save-to-knowledge-base-confirm-title")}
        centered
      >
        <Stack gap="md">
          <Text size="sm">{t("save-to-knowledge-base-confirm")}</Text>
          <Group justify="flex-end" gap="sm">
            <Button variant="default" onClick={close} disabled={saving}>
              {t("cancel")}
            </Button>
            <Button loading={saving} onClick={() => void handleSave()}>
              {t("save-to-knowledge-base")}
            </Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
