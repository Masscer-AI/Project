import React from "react";
import { SVGS } from "../../assets/svgs";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";

interface MessageProps {
  sender: string;
  text: string;
  imageUrl?: string;
  onGenerateSpeech: (text: string) => void;
  onGenerateImage: (text: string) => void;
}

export const Message: React.FC<MessageProps> = ({
  sender,
  text,
  imageUrl,
  onGenerateSpeech,
  onGenerateImage,
}) => {
  return (
    <div className={`message ${sender}`}>
      <MarkdownRenderer markdown={text} />
      {imageUrl && (
        <>
          <img src={imageUrl} alt="Generated" />
          <a href={imageUrl} download="generated-image">
            <button>{SVGS.download}</button>
          </a>
        </>
      )}
      <div className="message-buttons">
        <button onClick={() => onGenerateSpeech(text)}>{SVGS.waves}</button>
        <button onClick={() => onGenerateImage(text)}>{SVGS.image}</button>
      </div>
    </div>
  );
};
