import React, { useEffect, useState } from "react";
import { SVGS } from "../../assets/svgs";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { TAttachment } from "../../types";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import "./Message.css";
import { SvgButton } from "../SvgButton/SvgButton";
import toast from "react-hot-toast";
import { getChunk } from "../../modules/apiCalls";
import { Modal } from "../Modal/Modal";

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
  }, [text]);

  return (
    <div className={`message ${type} message-${index}`}>
      <MarkdownRenderer markdown={text} extraClass={"message-text"} />
      <section className="message__attachments">
        {attachments &&
          typeof attachments == "object" &&
          attachments.map(({ content, type }, index) => (
            // @ts-ignore
            <Thumbnail type={type} src={content} key={index} />
          ))}
        {sources &&
          sources.map((s, index) => (
            <Source key={index} text={s.text} href={s.url}></Source>
          ))}
      </section>
      <div className="message-buttons">
        <SvgButton onClick={() => onGenerateSpeech(text)} svg={SVGS.waves} />
        <SvgButton onClick={() => onGenerateImage(text)} svg={SVGS.image} />
        <SvgButton onClick={() => copyToClipboard(text)} svg={SVGS.copy} />
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
