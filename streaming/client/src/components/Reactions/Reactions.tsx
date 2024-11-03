import React from "react";
import { useStore } from "../../modules/store";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import { SvgButton } from "../SvgButton/SvgButton";
import { SVGS } from "../../assets/svgs";
import "./Reactions.css";
import { createReaction } from "../../modules/apiCalls";

export const Reactions = ({
  messageId,
  onReaction,
  currentReactions,
  direction = "right",
}: {
  messageId?: string;
  onReaction: (action: "add" | "remove", templateId: number) => void;
  currentReactions: number[];
  direction?: "left" | "right";
}) => {
  const { reactionTemplates } = useStore((s) => ({
    reactionTemplates: s.reactionTemplates,
  }));

  const handleReactionClick = (templateId: number) => {
    onReaction(
      currentReactions.includes(templateId) ? "remove" : "add",
      templateId
    );
    createReaction({
      template: String(templateId),
      message: messageId,
    });
  };

  return (
    <div className={`reactions-component from-${direction}`}>
      <SvgButton
        extraClass="dropdown-opener"
        title="Reactions"
        svg={SVGS.reaction}
      />
      <div className="d-flex rounded z-index-tap pos-absolute bg-secondary w-fit-content left reactions-dropdown">
        {reactionTemplates.map((reactionTemplate) => (
          <SvgButton
            extraClass={`${
              currentReactions.includes(reactionTemplate.id) && "bg-active"
            }`}
            onClick={() => handleReactionClick(reactionTemplate.id)}
            key={reactionTemplate.id}
            title={reactionTemplate.name}
            svg={reactionTemplate.emoji}
          />
        ))}
      </div>
    </div>
  );
};
