import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import { ActionIcon, Button, Group, Modal, Stack, Text, Tooltip } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconBooks } from "@tabler/icons-react";
import { addAttachmentToKnowledgeBase } from "../../modules/apiCalls";

export const KB_DOCUMENT_METADATA_KEY = "knowledge_base_document_id";

export function knowledgeBaseDocumentIdFromMetadata(
  metadata?: Record<string, unknown> | null
): number | null {
  const raw = metadata?.[KB_DOCUMENT_METADATA_KEY];
  if (typeof raw === "number" && Number.isFinite(raw) && raw > 0) {
    return raw;
  }
  if (typeof raw === "string" && raw.trim()) {
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed > 0) return parsed;
  }
  return null;
}

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

function knowledgeBaseHref(documentId: number): string {
  return `/knowledge-base?activeTab=documents&document=${encodeURIComponent(String(documentId))}`;
}

export function SaveToKnowledgeBaseButton({
  attachmentId,
  type,
  contentType,
  metadata,
  variant = "button",
  onIndexed,
}: {
  attachmentId?: string;
  type?: string;
  contentType?: string;
  metadata?: Record<string, unknown> | null;
  variant?: "button" | "icon";
  onIndexed?: (documentId: number) => void;
}) {
  const { t } = useTranslation();
  const [opened, { open, close }] = useDisclosure(false);
  const [saving, setSaving] = useState(false);
  const [indexedId, setIndexedId] = useState<number | null>(() =>
    knowledgeBaseDocumentIdFromMetadata(metadata)
  );

  useEffect(() => {
    const fromMeta = knowledgeBaseDocumentIdFromMetadata(metadata);
    if (fromMeta) setIndexedId(fromMeta);
  }, [metadata]);

  const linkedId = indexedId ?? knowledgeBaseDocumentIdFromMetadata(metadata);

  if (!canSaveAttachmentToKnowledgeBase(type, contentType)) {
    return null;
  }

  const handleSave = async () => {
    if (!attachmentId) return;
    setSaving(true);
    try {
      const result = await addAttachmentToKnowledgeBase(attachmentId);
      const documentId = result?.id;
      if (typeof documentId === "number" && documentId > 0) {
        setIndexedId(documentId);
        onIndexed?.(documentId);
      }
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

  if (linkedId) {
    const href = knowledgeBaseHref(linkedId);
    if (variant === "icon") {
      return (
        <Tooltip label={t("open-in-knowledge-base")}>
          <ActionIcon
            component={Link}
            to={href}
            variant="subtle"
            color="violet"
            size="sm"
            aria-label={t("open-in-knowledge-base")}
          >
            <IconBooks size={16} />
          </ActionIcon>
        </Tooltip>
      );
    }
    return (
      <Button
        component={Link}
        to={href}
        variant="light"
        color="violet"
        leftSection={<IconBooks size={16} />}
      >
        {t("in-knowledge-base")}
      </Button>
    );
  }

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
