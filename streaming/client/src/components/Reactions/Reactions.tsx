import React from "react";
import { useStore } from "../../modules/store";
import { createReaction } from "../../modules/apiCalls";
import { ActionIcon, Popover, Tooltip } from "@mantine/core";
import { IconMoodSmile } from "@tabler/icons-react";

export const Reactions = ({
  messageId,
  onReaction,
  currentReactions,
  direction = "right",
  maxReactions = 2,
}: {
  messageId?: string;
  onReaction: (action: "add" | "remove", templateId: number) => void;
  currentReactions: number[];
  direction?: "left" | "right";
  maxReactions?: number;
}) => {
  const { reactionTemplates } = useStore((s) => ({
    reactionTemplates: s.reactionTemplates,
  }));

  const handleReactionClick = (templateId: number) => {
    const action = currentReactions.includes(templateId) ? "remove" : "add";
    if (currentReactions.length >= maxReactions && action === "add") return;
    onReaction(action, templateId);
    createReaction({
      template: String(templateId),
      message: messageId,
    });
  };

  return (
    <Popover
      position={direction === "right" ? "bottom-end" : "bottom-start"}
      shadow="md"
      withArrow
    >
      <Popover.Target>
        <Tooltip label="Reactions" withArrow>
          <ActionIcon variant="subtle" color="gray" size="sm">
            <IconMoodSmile size={18} />
          </ActionIcon>
        </Tooltip>
      </Popover.Target>
      <Popover.Dropdown p={6}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 2 }}>
          {reactionTemplates.map((rt) => (
            <ActionIcon
              key={rt.id}
              variant={currentReactions.includes(rt.id) ? "filled" : "subtle"}
              color={currentReactions.includes(rt.id) ? "violet" : "gray"}
              size="md"
              onClick={() => handleReactionClick(rt.id)}
              title={rt.name}
            >
              <span style={{ fontSize: 16 }}>{rt.emoji}</span>
            </ActionIcon>
          ))}
        </div>
      </Popover.Dropdown>
    </Popover>
  );
};
