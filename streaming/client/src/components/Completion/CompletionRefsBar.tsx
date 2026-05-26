import React, { useMemo, useState } from "react";
import { Badge, Group, Stack, Text, UnstyledButton } from "@mantine/core";
import { IconFileText } from "@tabler/icons-react";
import { useTranslation } from "react-i18next";

import type { TAttachment, TSource } from "../../types";
import { useCompletionFreshApproval } from "../../hooks/useCompletionFreshApproval";
import { collectCompletionRefs } from "./completionUtils";
import { CompletionDetailModal } from "./CompletionDetailModal";

type Props = {
  attachments?: TAttachment[];
  sources?: TSource[];
  /** When set, parent renders CompletionDetailModal and handles open. */
  onOpenCompletion?: (
    id: string,
    fallback?: { content?: string; approved?: boolean }
  ) => void;
};

export const CompletionRefsBar = ({
  attachments,
  sources,
  onOpenCompletion,
}: Props) => {
  const { t } = useTranslation();
  const refs = useMemo(
    () => collectCompletionRefs(attachments, sources),
    [attachments, sources]
  );
  const freshApproval = useCompletionFreshApproval(refs.map((r) => r.id));

  const [modalId, setModalId] = useState<string | null>(null);
  const [modalFallback, setModalFallback] = useState<{
    content?: string;
    approved?: boolean;
  }>({});

  if (refs.length === 0) return null;

  const resolveFallback = (id: string) => {
    const source = sources?.find(
      (s) =>
        (s.model_name || "").toLowerCase() === "completion" &&
        String(s.model_id) === id
    );
    const att = attachments?.find(
      (a) =>
        (a.type || "").toLowerCase() === "completion" &&
        String(a.completion_id ?? a.id) === id
    );
    return {
      content: source?.content,
      approved: att?.approved,
    };
  };

  const openModal = (id: string) => {
    const fallback = resolveFallback(id);
    if (onOpenCompletion) {
      onOpenCompletion(id, fallback);
      return;
    }
    setModalFallback(fallback);
    setModalId(id);
  };

  return (
    <>
      {!onOpenCompletion && (
        <CompletionDetailModal
          completionId={modalId}
          opened={modalId != null}
          onClose={() => setModalId(null)}
          fallbackContent={modalFallback.content}
          fallbackApproved={modalFallback.approved}
        />
      )}

      <Stack gap={6} mt="xs">
        <Text size="xs" c="dimmed" fw={500}>
          {t("training-examples-used")}
        </Text>
        <Group gap="xs" wrap="wrap">
          {refs.map((ref) => {
            const approvedResolved =
              freshApproval[ref.id] !== undefined
                ? freshApproval[ref.id]
                : ref.approved;
            return (
              <UnstyledButton
                key={ref.id}
                onClick={() => openModal(ref.id)}
                style={{ maxWidth: "100%" }}
              >
                <Badge
                  variant="outline"
                  color="gray"
                  size="lg"
                  style={{ cursor: "pointer", maxWidth: "100%" }}
                  leftSection={<IconFileText size={14} />}
                  rightSection={
                    approvedResolved === false ? (
                      <Badge size="xs" color="yellow" variant="light" ml={4}>
                        {t("pending")}
                      </Badge>
                    ) : approvedResolved === true ? (
                      <Badge size="xs" color="green" variant="light" ml={4}>
                        {t("approved")}
                      </Badge>
                    ) : null
                  }
                >
                  <span>
                    {t("completion")} {ref.id}
                  </span>
                </Badge>
              </UnstyledButton>
            );
          })}
        </Group>
      </Stack>
    </>
  );
};
