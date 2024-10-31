import React, { useEffect, useRef, useState } from "react";
import { SVGS } from "../../assets/svgs";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { TAttachment } from "../../types";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import "./Message.css";
import { SvgButton } from "../SvgButton/SvgButton";
import toast from "react-hot-toast";
import { getChunk } from "../../modules/apiCalls";
import { Modal } from "../Modal/Modal";
import { useTranslation } from "react-i18next";
interface Link {
  url: string;
  text: string;
}

interface MessageProps {
  type: string;
  text: string;
  index: number;
  agentSlug?: string;
  attachments: TAttachment[];
  onGenerateSpeech: (text: string) => void;
  onGenerateImage: (text: string) => void;
}

export const Message: React.FC<MessageProps> = ({
  type,
  index,
  text,
  agentSlug,
  attachments,
  onGenerateSpeech,
  onGenerateImage,
}) => {
  const [sources, setSources] = useState([] as Link[]);
  const [isEditing, setIsEditing] = useState(false);
  const [innerText, setInnerText] = useState(text);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const { t } = useTranslation();
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

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        textareaRef.current.scrollHeight + "px";
    }
    return () => {
      if (textareaRef.current) {
        textareaRef.current.style.height = "auto";
      }
    };
  }, [innerText, isEditing]);

  useEffect(() => {
    const anchors = document.querySelectorAll(`.message-${index} a`);

    const extractedLinks: Link[] = Array.from(anchors).map((anchor) => ({
      url: anchor.getAttribute("href") || "",
      text: anchor.textContent || "",
    }));

    anchors.forEach((anchor) => {
      const href = anchor.getAttribute("href");
      if (!href) return;
      const isSource = href.includes("#");
      if (isSource) {
        anchor.removeAttribute("target");
      } else {
        anchor.setAttribute("target", "_blank");
      }
    });

    setSources(extractedLinks);
    setInnerText(text);
  }, [text]);

  const toggleEditMode = () => {
    setIsEditing(!isEditing);
  };

  return (
    <div className={`message ${type} message-${index}`}>
      <MarkdownRenderer
        contentEditable={isEditing}
        markdown={innerText}
        extraClass={"message-text"}
      />

      <section className="message__attachments">
        {attachments &&
          attachments.map(({ content, type, name }, index) => (
            <Thumbnail
              index={index}
              type={type}
              src={content}
              name={name}
              key={index}
            />
          ))}
        {sources &&
          sources.map((s, index) => (
            <Source key={index} text={s.text} href={s.url}></Source>
          ))}
      </section>
      <div className="message-buttons">
        <SvgButton
          title={t("generate-speech")}
          onClick={() => onGenerateSpeech(text)}
          svg={SVGS.waves}
        />
        <SvgButton
          title={t("generate-image")}
          onClick={() => onGenerateImage(text)}
          svg={SVGS.picture}
        />
        <SvgButton
          title={t("copy-to-clipboard")}
          onClick={() => copyToClipboard(text)}
          svg={SVGS.copyTwo}
        />
        <SvgButton
          title={isEditing ? t("finish") : t("edit")}
          onClick={toggleEditMode}
          svg={isEditing ? SVGS.finish : SVGS.edit}
        />

        {agentSlug ? agentSlug : ""}
      </div>
    </div>
  );
};

function getSomeNumberFromChunkString(chunkString) {
  // It must cut the string at - and return both parts
  const [modelName, modelId] = chunkString.split("-");
  return { modelName, modelId };
}

type TChunk = {
  id: number;
  document: number;
  content: string;
  brief?: string;
  tags?: string;
};
const Source = ({ href, text }) => {
  const [isVisible, setIsVisible] = useState(false);
  const [chunkInfo, setChunkInfo] = useState({} as TChunk);

  const sourceId = href.replace(/^#/, "");

  const handleGetModel = async () => {
    const { modelId, modelName } = getSomeNumberFromChunkString(href);
    const chunk = await getChunk(modelId);
    setChunkInfo(chunk);
    setIsVisible(true);
  };

  return (
    <div className="source-component">
      <input id={sourceId} type="text" />
      <h5>{text}</h5>
      <p>{href}</p>
      <SvgButton svg={SVGS.eyes} onClick={handleGetModel} />
      {isVisible && (
        <Modal visible={isVisible} hide={() => setIsVisible(false)}>
          <div className="chunk-info">
            <h3>{chunkInfo.brief}</h3>
            <textarea
              value={JSON.stringify(chunkInfo.content)}
              readOnly
              name="chunk_text"
            ></textarea>
          </div>
        </Modal>
      )}
    </div>
  );
};
