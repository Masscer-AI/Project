import React, { useCallback, useEffect, useRef, useState } from "react";
import { SVGS } from "../../assets/svgs";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { TAttachment, TSource, TVersion } from "../../types";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import "./Message.css";
import { SvgButton } from "../SvgButton/SvgButton";
import toast from "react-hot-toast";
import { deleteMessage, getChunk, updateMessage } from "../../modules/apiCalls";
import { Modal } from "../Modal/Modal";
import { useTranslation } from "react-i18next";
import { Pill } from "../Pill/Pill";
import { useStore } from "../../modules/store";
import { Reactions } from "../Reactions/Reactions";
import {
  AudioPlayerOptions,
  AudioPlayerWithAppendOptions,
  createAudioPlayer,
  createAudioPlayerWithAppend,
} from "../../modules/utils";
import { ImageGenerator } from "../ImageGenerator/ImageGenerator";
import { Loader } from "../Loader/Loader";
import { FloatingDropdown } from "../Dropdown/Dropdown";
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
  attachments: TAttachment[];

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

export const Message: React.FC<MessageProps> = ({
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
}) => {
  const [sources, setSources] = useState([] as Link[]);
  const [isEditing, setIsEditing] = useState(false);
  const [innerText, setInnerText] = useState(text);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
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

    // socket.on(`audio-chunk-${id}`, (data) => {
    //   toast.success("Audio chunk received");
    //   if (!audioPlayer) {
    //     const player = createAudioPlayerWithAppend(onFinishAudioGeneration);
    //     player.append(new Uint8Array(data.audio_bytes).buffer);
    //     if (data.position === 0) {
    //       setIsGeneratingSpeech(false);
    //       player.play();
    //     }
    //     setAudioPlayer(player);
    //   }
    // });
    return () => {
      socket.off(`audio-file-${id}`);
      // socket.off(`audio-chunk-${id}`);
    };
  }, [id, socket, audioPlayer]);

  useEffect(() => {
    if (
      id &&
      numberMessages === index + 1 &&
      userPreferences.autoplay &&
      type === "assistant"
    ) {
      handleGenerateSpeech();
    }
  }, [id, numberMessages]);

  useEffect(() => {
    if (isEditing && textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        textareaRef.current.scrollHeight + "px";

      textareaRef.current.setSelectionRange(
        textareaRef.current.value.length,
        textareaRef.current.value.length
      );
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
    // setSources(extractedLinks);
    setInnerText(text);
  }, [text]);

  const toggleEditMode = () => {
    if (isEditing) {
      textareaRef.current?.blur();
      // Get the textarea value
      const textareaValue = textareaRef.current?.value;

      if (id && type === "assistant" && versions && textareaValue) {
        const newVersions = versions.map((v, index) => {
          if (currentVersion === index) {
            return {
              ...v,
              text: textareaValue,
            };
          }
          return v;
        });

        updateMessage(id, {
          text: textareaValue,
          type: type,
          versions: newVersions,
        });
        onMessageEdit(index, textareaValue, newVersions);
      }
      if (id && type === "user" && textareaValue) {
        updateMessage(id, {
          text: textareaValue,
          type: type,
        });
        onMessageEdit(index, textareaValue);
      }
    }
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

  const handleGenerateSpeech = async () => {
    if (isGeneratingSpeech) {
      const randomWaitMessage = [
        t("speech-being-generated-wait-a-second"),
        t("are-you-trying-to-make-me-speak-twice?"),
        t("just-a-second"),
      ];
      const randomIndex = Math.floor(Math.random() * randomWaitMessage.length);
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
          text: versions?.[currentVersion]?.text || innerText,
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
    } else {
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

  return (
    <div className={`message ${type} message-${index}`}>
      {isEditing ? (
        <textarea
          autoComplete="on"
          ref={textareaRef}
          className="message-textarea"
          defaultValue={versions?.[currentVersion]?.text || innerText}
        />
      ) : (
        <MarkdownRenderer
          markdown={versions?.[currentVersion]?.text || innerText}
          extraClass={`message-text ${type === "user" ? "fancy-gradient" : ""}`}
        />
      )}

      {!id && type === "assistant" && <Loader text={t("thinking...")} />}
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
      <div className="message-buttons d-flex gap-small align-center">
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
                title={isEditing ? t("finish") : t("edit")}
                onClick={toggleEditMode}
                svg={isEditing ? SVGS.finish : SVGS.edit}
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
                    reactionTemplates.find((rt) => rt.id === r.template)?.emoji
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
          <Pill>{versions?.[currentVersion]?.agent_name}</Pill>
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
              {!audioPlayer && (
                <SvgButton
                  text={t("generate-speech")}
                  onClick={handleGenerateSpeech}
                  svg={SVGS.waves}
                  size="big"
                  extraClass="active-on-hover border-active pressable"
                />
              )}
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
const Source = ({ source }: { source: TSource }) => {
  const [isVisible, setIsVisible] = useState(false);

  const handleGetModel = async () => {
    // const { modelId, modelName } = getSomeNumberFromChunkString(href);
    // const chunk = await getChunk(modelId);
    // setChunkInfo(chunk);
    setIsVisible(true);
  };

  return (
    <div className="source-component">
      {/* <input type="text" /> */}
      <h5>
        {source.model_name} {source.model_id}
      </h5>

      <SvgButton svg={SVGS.eyes} onClick={handleGetModel} />
      {isVisible && (
        <Modal
          minHeight={"40vh"}
          visible={isVisible}
          hide={() => setIsVisible(false)}
        >
          <div className="chunk-info">
            <h3 className="text-center">
              {source.model_name} {source.model_id}
            </h3>
            <textarea
              value={JSON.stringify(source.content)}
              readOnly
              name="chunk_text"
            ></textarea>
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
    <div className="card bg-hovered">
      <p
        onClick={handleOpenWebsite}
        className="cut-text-to-line clickeable rounded padding-small"
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
    <div>
      <h3>{result.url}</h3>
      <p>{result.content}</p>
    </div>
  );
};
