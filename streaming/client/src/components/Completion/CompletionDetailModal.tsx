import React, { useEffect, useState } from "react";
import {
  Badge,
  Button,
  Group,
  Loader,
  Modal,
  Stack,
  Text,
  Title,
} from "@mantine/core";
import { IconExternalLink, IconFileText } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";

import { getCompletion } from "../../modules/apiCalls";
import type { TCompletion } from "../../types";
import { parseCompletionContent } from "./completionUtils";

type Props = {
  completionId: string | null;
  opened: boolean;
  onClose: () => void;
  /** Fallback when API fetch fails (e.g. from RAG source content). */
  fallbackContent?: string;
  fallbackApproved?: boolean;
};

export const CompletionDetailModal = ({
  completionId,
  opened,
  onClose,
  fallbackContent,
  fallbackApproved,
}: Props) => {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [completion, setCompletion] = useState<TCompletion | null>(null);

  useEffect(() => {
    if (!opened || !completionId) {
      setCompletion(null);
      return;
    }

    let cancelled = false;
    setLoading(true);
    getCompletion(completionId)
      .then((data) => {
        if (!cancelled) setCompletion(data);
      })
      .catch(() => {
        if (!cancelled) setCompletion(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [opened, completionId]);

  const parsedFallback = fallbackContent
    ? parseCompletionContent(fallbackContent)
    : { prompt: "", answer: "" };

  const prompt = completion?.prompt ?? parsedFallback.prompt;
  const answer = completion?.answer ?? parsedFallback.answer;
  const approved =
    completion?.approved ??
    (fallbackApproved !== undefined ? fallbackApproved : undefined);

  const openInKnowledgeBase = () => {
    if (!completionId) return;
    navigate(
      `/knowledge-base?activeTab=completions&completion=${encodeURIComponent(completionId)}`
    );
    onClose();
  };

  const copyText = `${t("prompt")}: ${prompt}\n\n${t("answer")}: ${answer}`;
  const copyAll = () => {
    navigator.clipboard.writeText(copyText).then(
      () => toast.success(t("message-copied")),
      () => toast.error(t("error-copying-message") || "Copy failed")
    );
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Group gap="xs">
          <IconFileText size={18} />
          <Text fw={600} size="sm">
            {t("completion")} {completionId}
          </Text>
          {approved === true && (
            <Badge size="xs" color="green" variant="light">
              {t("approved")}
            </Badge>
          )}
          {approved === false && (
            <Badge size="xs" color="yellow" variant="light">
              {t("pending")}
            </Badge>
          )}
        </Group>
      }
      centered
      size="lg"
    >
      {loading ? (
        <Stack align="center" py="xl">
          <Loader color="violet" size="sm" />
        </Stack>
      ) : (
        <Stack gap="md">
          <Stack gap={4}>
            <Title order={6} c="dimmed">
              {t("prompt")}
            </Title>
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
              {prompt || "—"}
            </Text>
          </Stack>

          <Stack gap={4}>
            <Title order={6} c="dimmed">
              {t("answer")}
            </Title>
            <Text size="sm" style={{ whiteSpace: "pre-wrap" }}>
              {answer || "—"}
            </Text>
          </Stack>

          <Group justify="flex-end" gap="xs">
            <Button variant="default" size="sm" onClick={copyAll}>
              {t("copy")}
            </Button>
            <Button
              variant="filled"
              size="sm"
              leftSection={<IconExternalLink size={16} />}
              onClick={openInKnowledgeBase}
            >
              {t("open-in-knowledge-base")}
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
};
