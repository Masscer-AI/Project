import React, { useEffect, useRef, useState, memo } from "react";
import { SVGS } from "../../assets/svgs";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { TAttachment, TSource, TVersion } from "../../types";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import { SvgButton } from "../SvgButton/SvgButton";
import toast from "react-hot-toast";
import { deleteMessage, updateMessage } from "../../modules/apiCalls";
import { Modal } from "../Modal/Modal";
import { useTranslation } from "react-i18next";
import { Pill } from "../Pill/Pill";
import { useStore } from "../../modules/store";
import { Reactions } from "../Reactions/Reactions";
import {
  AudioPlayerOptions,
  AudioPlayerWithAppendOptions,
  createAudioPlayer,
  // createAudioPlayerWithAppend,
} from "../../modules/utils";

import { ImageGenerator } from "../ImageGenerator/ImageGenerator";
import { Loader } from "../Loader/Loader";
import { FloatingDropdown } from "../Dropdown/Dropdown";
import { createPortal } from "react-dom";
import { AudioGenerator } from "../AudioGenerator/AudioGenerator";
type TReaction = {
  id: number;
  template: number;
};

interface Link {
  url: string;
  text: string;
}

const slugify = (text: string) => {
  return text
    .toLowerCase()
    .replace(/ /g, "-")
    .replace(/[^a-z0-9-]/g, "");
};

interface MessageProps {
  id?: number;
  type: string;
  text: string;
  index: number;
  versions?: TVersion[];
  attachments?: TAttachment[];

  onImageGenerated: (
    imageContentB64: string,
    imageName: string,
    message_id: number
  ) => void;
  onMessageEdit: (index: number, text: string, versions?: TVersion[]) => void;
  reactions?: TReaction[];
  onMessageDeleted: (index: number) => void;
  numberMessages: number;
}

export const Message = memo(
  ({
    type,
    index,
    id,
    text,
    versions,
    reactions,
    attachments,
    onImageGenerated,
    onMessageEdit,
    onMessageDeleted,
    numberMessages,
  }: MessageProps) => {
    const [isEditing, setIsEditing] = useState(false);
    const [innerText, setInnerText] = useState(text);
    const textareaValueRef = useRef<string | null>(null);
    const [currentVersion, setCurrentVersion] = useState(0);
    const [innerReactions, setInnerReactions] = useState(
      reactions || ([] as TReaction[])
    );
    const [audioPlayer, setAudioPlayer] = useState<
      AudioPlayerWithAppendOptions | AudioPlayerOptions | null
    >(null);
    const [isPlayingAudio, setIsPlayingAudio] = useState(false);
    const [messageState, setMessageState] = useState({
      imageGeneratorOpened: false,
    });
    const [isGeneratingSpeech, setIsGeneratingSpeech] = useState(false);

    const { t } = useTranslation();

    const { agents, reactionTemplates, socket, userPreferences } = useStore(
      (s) => ({
        agents: s.agents,
        reactionTemplates: s.reactionTemplates,
        socket: s.socket,
        userPreferences: s.userPreferences,

        // models: s.models,
      })
    );

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

    const onFinishAudioGeneration = () => {
      setIsPlayingAudio(false);
    };

    useEffect(() => {
      socket.on(`response-for-${index}`, (data) => {
        if (data.chunk) {
          setInnerText((prev) => prev + data.chunk);
        }
      });

      return () => {
        socket.off(`response-for-${index}`);
      };
    }, [index]);

    useEffect(() => {
      if (!id) return;

      socket.on(`audio-file-${id}`, (audioFile) => {
        setIsGeneratingSpeech(false);

        if (audioPlayer) {
          audioPlayer.stop();
          audioPlayer.destroy();
          // toast.success("Audio player stopped");
        }
        const newAudioPlayer = createAudioPlayer(
          audioFile,
          onFinishAudioGeneration
        );
        newAudioPlayer.play();

        setAudioPlayer(newAudioPlayer);
        setIsPlayingAudio(true);
      });

      return () => {
        socket.off(`audio-file-${id}`);
      };
    }, [id, socket, audioPlayer]);

    useEffect(() => {
      if (
        id &&
        numberMessages === index + 1 &&
        userPreferences.autoplay &&
        type === "assistant"
      ) {
        handleGenerateSpeech(versions?.[currentVersion]?.text || innerText);
      }
    }, [id, numberMessages]);

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
      // setSources(extractedLinks);
      setInnerText(text);
    }, [text]);

    const toggleEditMode = () => {
      setIsEditing(!isEditing);
    };

    const handleReaction = (action: "add" | "remove", templateId: number) => {
      if (action === "add") {
        setInnerReactions([
          ...innerReactions,
          { id: templateId, template: templateId },
        ]);
      } else {
        setInnerReactions(
          innerReactions.filter((r) => r.template !== templateId)
        );
      }
    };

    const handleGenerateSpeech = async (text: string) => {
      if (isGeneratingSpeech) {
        const randomWaitMessage = [
          t("speech-being-generated-wait-a-second"),
          t("are-you-trying-to-make-me-speak-twice?"),
          t("just-a-second"),
        ];
        const randomIndex = Math.floor(
          Math.random() * randomWaitMessage.length
        );
        toast.success(randomWaitMessage[randomIndex], {
          icon: "🔊",
        });
        return;
      }

      if (!audioPlayer) {
        try {
          toast.success(t("speech-being-generated-wait-a-second"), {
            icon: "🔊",
          });

          socket.emit("speech_request", {
            text: text,
            id: id,
            voice: {
              type: "openai",
              slug:
                agents.find(
                  (a) => versions?.[currentVersion].agent_slug === a.slug
                )?.openai_voice || "alloy",
            },
          });
          setIsGeneratingSpeech(true);
        } catch (error) {
          console.error("Error generating speech:", error);
        }
      }
    };

    const handleDelete = async () => {
      if (!id) return;
      try {
        await deleteMessage(id);
        onMessageDeleted(index);
      } catch (error) {
        console.error("Error deleting message:", error);
        toast.error(t("error-deleting-message"));
      }
    };

    const finishEditing = () => {
      const newValue = textareaValueRef.current;

      if (!newValue) {
        toggleEditMode();
        return;
      }

      setInnerText(newValue);

      if (id && type === "assistant" && versions && newValue) {
        const newVersions = versions.map((v, index) => {
          if (currentVersion === index) {
            return {
              ...v,
              text: newValue,
            };
          }
          return v;
        });

        updateMessage(id, {
          text: newValue,
          type: type,
          versions: newVersions,
        });
        onMessageEdit(index, newValue, newVersions);
      }
      if (id && type === "user" && newValue) {
        updateMessage(id, {
          text: newValue,
          type: type,
        });
        onMessageEdit(index, newValue);
      }

      toggleEditMode();
    };

    const handleMarkdownChange = (markdown: string) => {
      setInnerText(markdown);
    };

    return (
      <div className={`mb-5 max-w-[85%] flex flex-col relative group ${type === "user" ? "items-end ml-auto" : "items-start"} message-${index}`}>
        {isEditing ? (
          <>
            <MessageEditor
              textareaValueRef={textareaValueRef}
              text={versions?.[currentVersion]?.text || innerText}
              messageId={id}
              onImageGenerated={onImageGenerated}
            />
          </>
        ) : (
          <div className={`relative ${type === "user" ? "" : ""}`}>
            <MarkdownRenderer
              markdown={versions?.[currentVersion]?.text || innerText}
              // extraClass={`px-5 py-4 w-fit rounded-2xl text-white leading-7 overflow-x-auto scrollbar-none shadow-lg ${
              //   type === "user" 
              //     ? "bg-[#6e5bff] text-white border border-[#8b7aff] shadow-[0_4px_16px_rgba(110,91,255,0.4)]" 
              //     : "bg-[#1a1a2e] text-white border border-[#2d2d44] shadow-[0_4px_16px_rgba(0,0,0,0.4)]"
              // }`}
              extraClass={`px-5 py-4 w-fit rounded-2xl text-white leading-7 overflow-x-auto scrollbar-none shadow-lg backdrop-blur-md ${
                type === "user" 
                  ? "bg-gradient-to-b from-[rgba(0,130,146,0.6)] to-[rgba(50,18,122,0.6)] text-white border border-[rgba(0,130,146,0.3)] shadow-[0_4px_16px_rgba(50,18,122,0.25)]" 
                  : "bg-[rgba(35,33,39,0.5)] text-white border border-[rgba(255,255,255,0.1)] shadow-[0_4px_16px_rgba(0,0,0,0.3)]"
              }`}
            />
          </div>
        )}

        {!id && type === "assistant" && <Loader text={t("thinking...")} />}
        <section className={`flex gap-2.5 overflow-x-auto p-2 w-fit items-center rounded-xl mt-2 ${type === "user" ? "flex-row-reverse" : ""}`}>
          {attachments &&
            attachments.map((attachment, index) => (
              <Thumbnail
                {...attachment}
                index={index}
                // type={type}
                src={attachment.content}
                // name={name}
                key={index}
                message_id={id}
              />
            ))}
          {versions?.[currentVersion]?.sources &&
            versions?.[currentVersion]?.sources.map((s, index) => (
              <Source key={index} source={s} />
            ))}

          {versions?.[currentVersion]?.web_search_results &&
            versions?.[currentVersion]?.web_search_results.map(
              (result, index) => {
                if (!result) return null;
                return <WebSearchResultInspector key={index} result={result} />;
              }
            )}
        </section>
        <div className={`flex gap-2.5 items-center flex-wrap mt-3 opacity-0 group-hover:opacity-100 transition-all duration-300 ${type === "assistant" ? "pl-0" : ""}`}>
          <SvgButton
            title={t("copy-to-clipboard")}
            extraClass="active-on-hover  pressable"
            onClick={() => copyToClipboard()}
            svg={SVGS.copyTwo}
            // text={t("copy")}
            // size="big"
          />
          {id && (
            <>
              {messageState.imageGeneratorOpened && (
                <ImageGenerator
                  onResult={(imageB64, imageName) =>
                    onImageGenerated(imageB64, imageName, id)
                  }
                  messageId={id}
                  hide={() =>
                    setMessageState((prev) => ({
                      ...prev,
                      imageGeneratorOpened: false,
                    }))
                  }
                  initialPrompt={versions?.[currentVersion]?.text || innerText}
                />
              )}

              {audioPlayer && (
                <>
                  {isPlayingAudio ? (
                    <SvgButton
                      title={t("pause-speech")}
                      onClick={() => {
                        audioPlayer.pause();
                        setIsPlayingAudio(false);
                      }}
                      svg={SVGS.pause}
                    />
                  ) : (
                    <SvgButton
                      title={t("play-speech")}
                      onClick={() => {
                        audioPlayer.play();
                        setIsPlayingAudio(true);
                      }}
                      svg={SVGS.play}
                    />
                  )}
                  <SvgButton
                    title={t("stop-speech")}
                    onClick={() => {
                      audioPlayer.stop();
                      setIsPlayingAudio(false);
                    }}
                    svg={SVGS.stop}
                  />
                  <SvgButton
                    title={t("download-audio")}
                    onClick={() => {
                      const filename = slugify(
                        versions?.[currentVersion]?.text || text
                      ).slice(0, 100);

                      audioPlayer.download(filename);
                    }}
                    svg={SVGS.download}
                  />
                </>
              )}
              {isEditing && (
                <SvgButton
                  title={t("finish")}
                  onClick={finishEditing}
                  svg={SVGS.finish}
                  extraClass={isEditing ? "bg-active" : ""}
                />
              )}
              <Reactions
                direction={type === "user" ? "right" : "left"}
                onReaction={handleReaction}
                messageId={id.toString()}
                currentReactions={innerReactions?.map((r) => r.template) || []}
              />
              {innerReactions && innerReactions.length > 0 && (
                <>
                  {innerReactions.map(
                    (r) =>
                      reactionTemplates.find((rt) => rt.id === r.template)
                        ?.emoji
                  )}
                </>
              )}
            </>
          )}

          {versions && (
            <div className="d-flex gap-small align-center">
              {versions.map((v, index) => (
                <Pill
                  key={index + "pill"}
                  extraClass={`${
                    currentVersion === index ? "bg-active" : "bg-hovered"
                  }`}
                  onClick={() => {
                    setCurrentVersion(index);
                    setAudioPlayer(null);
                  }}
                >
                  <span className="box">{index + 1}</span>
                </Pill>
              ))}
            </div>
          )}

          {versions?.[currentVersion]?.agent_name ? (
            <FloatingDropdown
              left="50%"
              bottom="100%"
              transform="translateX(-50%)"
              opener={<Pill>{versions?.[currentVersion]?.agent_name}</Pill>}
            >
              <div className="flex-y gap-small width-150">
                <h4 className="text-center">Tokens</h4>

                <p>
                  <span className="text-secondary">Prompt:</span>{" "}
                  {versions?.[currentVersion]?.usage?.prompt_tokens}
                </p>
                <p>
                  <span className="text-secondary">Completion:</span>{" "}
                  {versions?.[currentVersion]?.usage?.completion_tokens}
                </p>
                <p>
                  <span className="text-secondary">Total:</span>{" "}
                  {versions?.[currentVersion]?.usage?.total_tokens}
                </p>

                {versions?.[currentVersion]?.usage?.model_slug && (
                  <Pill extraClass="bg-hovered w-100 text-center">
                    {versions?.[currentVersion]?.usage?.model_slug}
                  </Pill>
                )}
              </div>
            </FloatingDropdown>
          ) : null}

          {id && (
            <FloatingDropdown
              {...(index === 0
                ? { right: "100%", top: "0" }
                : {
                    right: "0",
                    bottom: "100%",
                  })}
              opener={<SvgButton svg={SVGS.options} />}
            >
              <div className="flex-y gap-small width-200">
                {/* {!audioPlayer && (
                  <SvgButton
                    text={t("generate-speech")}
                    onClick={() =>
                      handleGenerateSpeech(
                        versions?.[currentVersion]?.text || innerText
                      )
                    }
                    svg={SVGS.waves}
                    size="big"
                    extraClass="active-on-hover border-active pressable"
                  />
                )} */}
                <AudioGenerator
                  text={versions?.[currentVersion]?.text || innerText}
                  messageId={id.toString()}
                />

                <SvgButton
                  title={isEditing ? t("finish") : t("edit")}
                  onClick={toggleEditMode}
                  size="big"
                  text={isEditing ? t("finish") : t("edit")}
                  svg={isEditing ? SVGS.finish : SVGS.edit}
                  extraClass="active-on-hover border-active pressable"
                />
                <SvgButton
                  size="big"
                  text={t("generate-image")}
                  extraClass="active-on-hover border-active pressable"
                  onClick={() =>
                    setMessageState((prev) => ({
                      ...prev,
                      imageGeneratorOpened: true,
                    }))
                  }
                  svg={SVGS.picture}
                />
                <SvgButton
                  title={t("delete-message")}
                  size="big"
                  extraClass="border-danger danger-on-hover  pressable"
                  onClick={() => handleDelete()}
                  svg={SVGS.trash}
                  text={t("delete")}
                  confirmations={[t("im-sure")]}
                />
              </div>
            </FloatingDropdown>
          )}
        </div>
      </div>
    );
  }
);

const Source = ({ source }: { source: TSource }) => {
  const [isVisible, setIsVisible] = useState(false);

  const { t } = useTranslation();
  const handleGetModel = async () => {
    setIsVisible(true);
  };

  return (
    <div className="p-3 rounded-xl border border-[#2d2d44] bg-[#1a1a2e] relative shadow-md">
      <input id={`${source.model_name}-${source.model_id}`} type="text" className="w-0 h-0 absolute bg-transparent border-none outline-none" />
      <p className="w-fit truncate text-sm">
        <span className="text-white font-medium">{t("source")}: </span>
        <span className="text-[#9ca3af]">
          {t(source.model_name)} {source.model_id}
        </span>
      </p>

      <div className="flex justify-center mt-2">
        <SvgButton
          size="big"
          text={t("inspect")}
          svg={SVGS.eyes}
          onClick={handleGetModel}
        />
      </div>
      {isVisible && (
        <Modal
          minHeight={"40vh"}
          visible={isVisible}
          hide={() => setIsVisible(false)}
        >
          <div className="flex flex-col gap-6">
            <h2 className="text-center">
              {t(source.model_name)} {source.model_id}
            </h2>
            <pre>{source.content}</pre>
          </div>
        </Modal>
      )}
    </div>
  );
};

const WebSearchResultInspector = ({ result }) => {
  const { t } = useTranslation();
  const [isVisible, setIsVisible] = useState(false);

  const handleOpenWebsite = () => {
    window.open(result.url, "_blank");
  };
  return (
    <div className="bg-[#1a1a2e] rounded-xl p-4 border border-[#2d2d44] shadow-md">
      <p
        onClick={handleOpenWebsite}
        className="truncate cursor-pointer rounded-lg p-3 bg-[#0f0f1a] hover:bg-[#252540] border border-[#2d2d44] hover:border-[#6e5bff] transition-all text-sm text-[#9ca3af] hover:text-white"
        title={result.url}
      >
        {result.url}
      </p>
      <SvgButton
        size="big"
        text={t("inspect-content")}
        svg={SVGS.webSearch}
        onClick={() => setIsVisible(true)}
      />
      {isVisible && (
        <Modal
          minHeight={"40vh"}
          visible={isVisible}
          hide={() => setIsVisible(false)}
        >
          <WebSearchResultContent result={result} />
        </Modal>
      )}
    </div>
  );
};

const WebSearchResultContent = ({ result }) => {
  return (
    <div className="flex flex-col gap-4">
      <h2 className="break-all">{result.url}</h2>
      <pre className="break-all">{result.content}</pre>
    </div>
  );
};

{
  /* <textarea
autoComplete="on"
ref={textareaRef}
className="message-textarea"
defaultValue={versions?.[currentVersion]?.text || innerText}
/> */
}

const MessageEditor = ({
  text,
  textareaValueRef,
  messageId,
  onImageGenerated,
}) => {
  const [innerText, setInnerText] = useState(text);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [editionOptions, setEditionOptions] = useState({
    top: 0,
    left: 0,
    isVisible: false,
    generateImage: false,
    currentText: text,
  });
  const { t } = useTranslation();

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        textareaRef.current.scrollHeight + "px";
    }
  }, [innerText]);

  const handleDoubleClick = (e: React.MouseEvent<HTMLTextAreaElement>) => {
    // Get current selected text
    const selectedText = window.getSelection()?.toString();

    if (selectedText) {
      setEditionOptions({
        top: e.clientY,
        left: e.clientX,
        isVisible: true,
        generateImage: false,
        currentText: selectedText,
      });
    } else {
      setEditionOptions({
        top: e.clientY,
        left: e.clientX,
        isVisible: false,
        generateImage: false,
        currentText: text,
      });
    }
  };

  const generateImageWithThisText = () => {
    setEditionOptions((prev) => ({
      ...prev,
      generateImage: true,
    }));
  };

  const handleTouchEnd = (e: React.TouchEvent<HTMLTextAreaElement>) => {
    console.log(e);
    const selectedText = window.getSelection()?.toString();

    if (e.changedTouches.length === 0) return;

    const touch = e.changedTouches[0];
    if (selectedText && touch) {
      setEditionOptions({
        top: touch.clientY,
        left: touch.clientX,
        isVisible: true,
        generateImage: false,
        currentText: selectedText,
      });
    }
  };

  return (
    <div className="w-full">
      <textarea
        autoComplete="on"
        ref={textareaRef}
        className="w-full px-4 py-3 font-sans rounded-xl text-base leading-6 scrollbar-none border border-[#6e5bff]/30 bg-[#0f0f1a] text-white resize-none focus:outline-none focus:border-[#6e5bff] focus:ring-2 focus:ring-[#6e5bff]/20"
        onChange={(e) => {
          textareaValueRef.current = e.target.value;
          setInnerText(e.target.value);
        }}
        defaultValue={text}
        onMouseUp={handleDoubleClick}
        // onDoubleClick={handleDoubleClick}
        onTouchEnd={handleTouchEnd}
        // onTouchEnd={handleTouchEnd}
      />
      {editionOptions.isVisible &&
        createPortal(
          <div
            style={{
              top: editionOptions.top,
              left: editionOptions.left,
            }}
            className="absolute w-fit bg-[#1a1a2e] border border-[#2d2d44] rounded-xl p-3 shadow-[0_8px_24px_rgba(0,0,0,0.6)]"
          >
            {editionOptions.generateImage && (
              <ImageGenerator
                onResult={(imageB64, imageName) =>
                  onImageGenerated(imageB64, imageName, messageId)
                }
                messageId={messageId}
                hide={() =>
                  setEditionOptions((prev) => ({
                    ...prev,
                    generateImage: false,
                  }))
                }
                initialPrompt={editionOptions.currentText}
              />
            )}
            <SvgButton
              text={t("generate-image")}
              onClick={generateImageWithThisText}
              svg={SVGS.picture}
              size="big"
            />
            {/* <SvgButton
              text={t("generate-speech")}
              onClick={generateSpeechWithThisText}
              svg={SVGS.waves}
              size="big"
            /> */}
            <AudioGenerator
              text={editionOptions.currentText}
              messageId={messageId}
            />
            <ModifyTextModal
              text={editionOptions.currentText}
              // messageID={messageId}
            />
          </div>,
          document.body
        )}
    </div>
  );
};

const ModifyTextModal = ({ text }) => {
  const [isVisible, setIsVisible] = useState(false);
  // const [modifications, setModifications] = useState({
  //   text: text,
  //   messageID: messageID,
  // });
  const { t } = useTranslation();

  return (
    <>
      <SvgButton
        size="big"
        text={t("modify-text")}
        onClick={() => setIsVisible(true)}
        svg={SVGS.edit}
      />
      <Modal
        header={<h3 className="padding-medium">{t("modify-message")}</h3>}
        visible={isVisible}
        hide={() => setIsVisible(false)}
      >
        <div className="flex-y gap-medium">
          <h4>{t("selected-text")}</h4>
          <p className="text-small text-secondary">{text}</p>
          <div className="d-flex gap-small">
            <SvgButton text="Extend" svg={SVGS.plus} />
          </div>
        </div>
      </Modal>
    </>
  );
};
