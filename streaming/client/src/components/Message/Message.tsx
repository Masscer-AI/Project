import React from "react";
import { SVGS } from "../../assets/svgs";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { TAttachment } from "../../types";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import "./Message.css";

interface MessageProps {
  type: string;
  text: string;
  attachments: TAttachment[];
  onGenerateSpeech: (text: string) => void;
  onGenerateImage: (text: string) => void;
}

export const Message: React.FC<MessageProps> = ({
  type,
  text,
  attachments,
  onGenerateSpeech,
  onGenerateImage,
}) => {
  return (
    <div className={`message ${type}`}>
      <MarkdownRenderer markdown={text} />
      <section className="message__attachments">
        {attachments &&
          attachments.map(({ content, type }, index) => (
            <Thumbnail type={type} src={content} key={index} />
          ))}
      </section>
      <div className="message-buttons">
        <button onClick={() => onGenerateSpeech(text)}>{SVGS.waves}</button>
        <button onClick={() => onGenerateImage(text)}>{SVGS.image}</button>
      </div>
    </div>
  );
};
