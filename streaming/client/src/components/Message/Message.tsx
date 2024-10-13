import React from "react";
import { SVGS } from "../../assets/svgs";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { TAttachment } from "../../types";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import "./Message.css";
import { SvgButton } from "../SvgButton/SvgButton";
import toast from "react-hot-toast";

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
  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => {
        toast.success("Message copied to clipboard!");
      },
      (err) => {
        console.error("Error al copiar al portapapeles: ", err);
      }
    );
  };

  return (
    <div className={`message ${type}`}>
      <MarkdownRenderer markdown={text} />
      <section className="message__attachments">
        {attachments &&
          typeof attachments == "object" &&
          attachments.map(({ content, type }, index) => (
            // @ts-ignore
            <Thumbnail type={type} src={content} key={index} />
          ))}
      </section>
      <div className="message-buttons">
        <SvgButton onClick={() => onGenerateSpeech(text)} svg={SVGS.waves} />
        <SvgButton onClick={() => onGenerateImage(text)} svg={SVGS.image} />
        <SvgButton onClick={() => copyToClipboard(text)} svg={SVGS.copy} />
      </div>
    </div>
  );
};
