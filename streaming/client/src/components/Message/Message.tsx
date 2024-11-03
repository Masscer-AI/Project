import React, { useEffect, useRef, useState } from "react";
import { SVGS } from "../../assets/svgs";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { TAttachment } from "../../types";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import "./Message.css";
import { SvgButton } from "../SvgButton/SvgButton";
import toast from "react-hot-toast";
import { getChunk, updateMessage } from "../../modules/apiCalls";
import { Modal } from "../Modal/Modal";
import { useTranslation } from "react-i18next";
import { Pill } from "../Pill/Pill";
import { useStore } from "../../modules/store";
interface Link {
  url: string;
  text: string;
}

interface MessageProps {
  id?: number;
  type: string;
  text: string;
  index: number;
  agent_slug?: string;
  versions?: {
    text: string;
    type: string;
    agent_slug: string;
  }[];
  attachments: TAttachment[];
  onGenerateSpeech: (text: string) => void;
  onGenerateImage: (text: string) => void;
}

export const Message: React.FC<MessageProps> = ({
  type,
  index,
  id,
  text,
  agent_slug,
  versions,
  attachments,
  onGenerateSpeech,
  onGenerateImage,
}) => {
  const [sources, setSources] = useState([] as Link[]);
  const [isEditing, setIsEditing] = useState(false);
  const [innerText, setInnerText] = useState(text);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [currentVersion, setCurrentVersion] = useState(0);

  const { t } = useTranslation();

  const { agents } = useStore((s) => ({
    agents: s.agents,
  }));
  const copyToClipboard = () => {
    const textToCopy = versions?.[currentVersion]?.text || innerText;
    navigator.clipboard.writeText(textToCopy).then(
      () => {
        toast.success(t("message-copied"));
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

    const extractedLinks: Link[] = [];

    anchors.forEach((anchor) => {
      const href = anchor.getAttribute("href");
      if (!href) return;
      const isSource = href.includes("#");
      if (isSource) {
        anchor.removeAttribute("target");
      } else {
        anchor.setAttribute("target", "_blank");
      }
      const currentHrefs = extractedLinks.map((l) => l.url);
      if (!currentHrefs.includes(href)) {
        extractedLinks.push({ url: href, text: anchor.textContent || "" });
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
        markdown={versions?.[currentVersion]?.text || innerText}
        extraClass={`message-text ${type === "user" ? "fancy-gradient" : ""}`}
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
      <div className="message-buttons d-flex gap-small align-center">
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
          onClick={() => copyToClipboard()}
          svg={SVGS.copyTwo}
        />
        {id && (
          <>
            <SvgButton
              title={isEditing ? t("finish") : t("edit")}
              onClick={toggleEditMode}
              svg={isEditing ? SVGS.finish : SVGS.edit}
            />
            <SvgButton
              title={t("thumb-up")}
              onClick={() => updateMessage(id, { thumbs_up: true })}
              svg={SVGS.thumbUp}
            />
            <SvgButton
              title={t("thumb-down")}
              onClick={() => toast.success(`thumb down to message ${id}`)}
              svg={SVGS.thumbDown}
            />
          </>
        )}

        {versions && (
          <div className="d-flex gap-small align-center">
            {versions.map((v, index) => (
              <Pill
                key={index + "pill"}
                extraClass={` ${
                  currentVersion === index ? "bg-active" : "bg-hovered"
                }`}
                onClick={() => setCurrentVersion(index)}
              >
                {index + 1}
              </Pill>
            ))}
          </div>
        )}
        {versions?.[currentVersion]?.agent_slug ? (
          <Pill>
            {
              agents.find((a) => a.slug === versions[currentVersion].agent_slug)
                ?.name
            }
          </Pill>
        ) : null}
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
        <Modal
          minHeight={"40vh"}
          visible={isVisible}
          hide={() => setIsVisible(false)}
        >
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
