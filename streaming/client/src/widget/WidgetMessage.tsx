import React, { memo } from "react";
import WidgetMarkdownRenderer from "./WidgetMarkdownRenderer";
import { WidgetThumbnail } from "./WidgetThumbnail";
import "./WidgetMessage.css";

interface WidgetMessageProps {
  id?: number;
  type: string;
  text: string;
  index: number;
  versions?: { text?: string; agent_slug?: string; agent_name?: string }[];
  attachments?: { type: string; content: string; name: string; text?: string; attachment_id?: string | number; id?: string | number }[];
  numberMessages: number;
  isLastAssistantInProgress?: boolean;
  agentTaskStatus?: string | null;
}

export const WidgetMessage = memo(
  ({
    type,
    index,
    id,
    text,
    versions,
    attachments,
    isLastAssistantInProgress,
    agentTaskStatus,
  }: WidgetMessageProps) => {
    const currentVersion = versions && versions.length > 0 ? versions.length - 1 : 0;
    const contentToRender = versions?.[currentVersion]?.text || text;

    return (
      <div className={`message ${type} message-${index}`}>
        <div className={`message-text ${type}`}>
          <WidgetMarkdownRenderer
            markdown={contentToRender}
            extraClass={`message-content ${type}`}
            attachments={attachments}
          />
        </div>

        {isLastAssistantInProgress && (
          <div className="chat-widget-loader">
            <div className="chat-widget-loader-spinner" />
            <span>{agentTaskStatus || "Thinking..."}</span>
          </div>
        )}

        <section className="message__attachments">
          {attachments &&
            attachments.map((attachment, i) => (
              <WidgetThumbnail
                {...attachment}
                index={i}
                src={attachment.content}
                key={i}
                message_id={id}
              />
            ))}
        </section>
      </div>
    );
  }
);

