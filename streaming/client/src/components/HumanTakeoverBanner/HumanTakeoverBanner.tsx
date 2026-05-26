import React, { useState } from "react";
import { Alert, Button, Group, Text } from "@mantine/core";
import { useTranslation } from "react-i18next";
import toast from "react-hot-toast";
import {
  releaseConversationTakeover,
  startConversationTakeover,
} from "../../modules/apiCalls";
import type { TConversation, TConversationActiveTakeover } from "../../types";

type HumanTakeoverBannerProps = {
  conversationId: string;
  activeTakeover: TConversationActiveTakeover | null | undefined;
  canTakeOver: boolean;
  isTakeoverOperator: boolean;
  onConversationUpdated: (conversation: TConversation) => void;
};

export const HumanTakeoverBanner: React.FC<HumanTakeoverBannerProps> = ({
  conversationId,
  activeTakeover,
  canTakeOver,
  isTakeoverOperator,
  onConversationUpdated,
}) => {
  const { t } = useTranslation();
  const [loading, setLoading] = useState(false);

  if (!canTakeOver && !isTakeoverOperator && !activeTakeover) {
    return null;
  }

  const handleTakeOver = async () => {
    setLoading(true);
    try {
      const updated = await startConversationTakeover(conversationId);
      onConversationUpdated(updated as TConversation);
      toast.success(t("human-takeover-started"));
    } catch (error: unknown) {
      const status = (error as { response?: { status?: number } })?.response
        ?.status;
      if (status === 409) {
        toast.error(t("human-takeover-conflict"));
      } else {
        toast.error(t("human-takeover-failed"));
      }
    } finally {
      setLoading(false);
    }
  };

  const handleRelease = async () => {
    setLoading(true);
    try {
      const updated = await releaseConversationTakeover(conversationId);
      onConversationUpdated(updated as TConversation);
      toast.success(t("human-takeover-released"));
    } catch {
      toast.error(t("human-takeover-failed"));
    } finally {
      setLoading(false);
    }
  };

  if (isTakeoverOperator) {
    return (
      <Alert color="violet" variant="light" radius="md" mb="sm">
        <Group justify="space-between" wrap="nowrap" gap="sm">
          <Text size="sm">{t("human-takeover-active-self")}</Text>
          <Button
            size="xs"
            variant="default"
            loading={loading}
            onClick={() => void handleRelease()}
          >
            {t("release-conversation")}
          </Button>
        </Group>
      </Alert>
    );
  }

  if (activeTakeover?.status === "ACTIVE") {
    return (
      <Alert color="gray" variant="light" radius="md" mb="sm">
        <Text size="sm">
          {t("human-takeover-active-by", {
            name: activeTakeover.operator_display_name,
          })}
        </Text>
      </Alert>
    );
  }

  if (canTakeOver) {
    return (
      <Alert color="blue" variant="light" radius="md" mb="sm">
        <Group justify="space-between" wrap="nowrap" gap="sm">
          <Text size="sm">{t("human-takeover-prompt")}</Text>
          <Button
            size="xs"
            variant="filled"
            loading={loading}
            onClick={() => void handleTakeOver()}
          >
            {t("take-over-conversation")}
          </Button>
        </Group>
      </Alert>
    );
  }

  return null;
};
