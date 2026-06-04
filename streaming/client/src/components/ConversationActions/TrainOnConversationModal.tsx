import React, { useState } from "react";
import {
  Modal,
  Button,
  NumberInput,
  Badge,
  Group,
  Stack,
  Text,
} from "@mantine/core";
import { IconBarbell } from "@tabler/icons-react";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";
import { useStore } from "../../modules/store";
import { generateTrainingCompletions } from "../../modules/apiCalls";
import { TConversation } from "../../types";

export const TrainOnConversationModal = ({
  opened,
  onClose,
  conversation,
}: {
  opened: boolean;
  onClose: () => void;
  conversation: TConversation;
}) => {
  const { t } = useTranslation();
  const { agents } = useStore((state) => ({
    agents: state.agents,
  }));

  const [selectedAgents, setSelectedAgents] = useState<string[]>([]);
  const [completionsTargetNumber, setCompletionsTargetNumber] = useState(30);

  const toggleAgent = (slug: string) => {
    if (selectedAgents.includes(slug)) {
      setSelectedAgents((prev) => prev.filter((s) => s !== slug));
    } else {
      setSelectedAgents((prev) => [...prev, slug]);
    }
  };

  const generateTrainingData = async () => {
    if (selectedAgents.length === 0) {
      toast.error(t("please-select-at-least-one-agent"));
      return;
    }

    await generateTrainingCompletions({
      model_id: conversation.id,
      db_model: "conversation",
      agents: selectedAgents,
      completions_target_number: completionsTargetNumber,
    });
    toast.success(t("training-generation-in-queue"));
    onClose();
  };

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      onExitTransitionEnd={() => {
        setSelectedAgents([]);
        setCompletionsTargetNumber(30);
      }}
      title={t("generate-completions")}
      centered
    >
      <Stack gap="md">
        <Text>
          {t("generate-completions-description")}{" "}
          <strong>{conversation.title}</strong>{" "}
          {t("generate-completions-description-2")}
        </Text>
        <Text>{t("after-generating-completions")}</Text>
        <NumberInput
          label={t("number-of-completions-to-generate")}
          value={completionsTargetNumber}
          onChange={(val) =>
            setCompletionsTargetNumber(typeof val === "number" ? val : 30)
          }
          min={1}
          variant="filled"
        />
        <Text size="sm">{t("select-agents-that-will-retrain")}</Text>
        <Group gap="xs" wrap="wrap">
          {agents.map((a) => (
            <Badge
              key={a.id}
              variant={
                selectedAgents.includes(a.slug) ? "filled" : "default"
              }
              style={{ cursor: "pointer" }}
              onClick={() => toggleAgent(a.slug)}
            >
              {a.name}
            </Badge>
          ))}
        </Group>
        <Button
          leftSection={<IconBarbell size={18} />}
          onClick={generateTrainingData}
          fullWidth
        >
          {t("generate")}
        </Button>
      </Stack>
    </Modal>
  );
};
