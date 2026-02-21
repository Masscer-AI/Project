import React, { memo } from "react";
import MarkdownRenderer from "../components/MarkdownRenderer/MarkdownRenderer";
import { TAttachment } from "../types";
import { Thumbnail } from "../components/Thumbnail/Thumbnail";
import { TVersion } from "../types";
import "./WidgetMessage.css";

// Simplified version of Message for the widget
// Removes dependencies on global store, complex actions, and i18n

interface WidgetMessageProps {
  id?: number;
  type: string;
  text: string;
  index: number;
  versions?: TVersion[];
  attachments?: TAttachment[];
  numberMessages: number;
}

export const WidgetMessage = memo(
  ({
    type,
    index,
    id,
    text,
    versions,
    attachments,
  }: WidgetMessageProps) => {
    // Use the latest version text if available, otherwise fallback to text prop
    const currentVersion = versions && versions.length > 0 ? versions.length - 1 : 0;
    const contentToRender = versions?.[currentVersion]?.text || text;

    return (
      <div className={`message ${type} message-${index}`}>
        <div className={`message-text ${type}`}>
          <MarkdownRenderer
            markdown={contentToRender}
            extraClass={`message-content ${type}`}
            attachments={attachments}
          />
        </div>

        {/* Attachments */}
        <section className="message__attachments">
          {attachments &&
            attachments.map((attachment, i) => (
              <Thumbnail
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

