import React, { useEffect, useRef } from "react";
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
  const divRef = useRef<HTMLDivElement>(null);

  const handleReactionClick = (templateId: number) => {
    const action = currentReactions.includes(templateId) ? "remove" : "add";
    if (currentReactions.length >= maxReactions && action === "add") return;
    onReaction(action, templateId);
    createReaction({
      template: String(templateId),
      message: messageId,
    });
  };

  useEffect(() => {
    // Adjust the width to never overflow
    // calculate with respect of the left border and the right border ;=less than 100px
    if (divRef.current) {
      const left = divRef.current.offsetLeft;
      const width = divRef.current.offsetWidth;
    }
  }, [currentReactions]);

  return (
    <div className={`reactions-component from-${direction}`}>
      <SvgButton
        extraClass="dropdown-opener"
        title="Reactions"
        svg={SVGS.reaction}
      />
      <div
        ref={divRef}
        className="d-flex rounded z-index-tap pos-absolute bg-secondary wrap-wrap width-150 reactions-dropdown"
      >
        {reactionTemplates.map((reactionTemplate) => (
          <SvgButton
            extraClass={`${
              currentReactions.includes(reactionTemplate.id) &&
              "bg-active pressable"
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
