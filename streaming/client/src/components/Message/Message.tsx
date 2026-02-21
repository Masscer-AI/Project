import React, { useEffect, useRef, useState, memo } from "react";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { TAttachment, TAgentSession, TSource, TVersion } from "../../types";
import { API_URL } from "../../modules/constants";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import toast from "react-hot-toast";
import { deleteMessage, updateMessage, getAgentSessionsForMessage } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { useStore } from "../../modules/store";
import { Reactions } from "../Reactions/Reactions";
import {
  AudioPlayerOptions,
  AudioPlayerWithAppendOptions,
  createAudioPlayer,
} from "../../modules/utils";

import { ImageGenerator } from "../ImageGenerator/ImageGenerator";
import { createPortal } from "react-dom";
import { AudioGenerator } from "../AudioGenerator/AudioGenerator";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import "./Message.css";

import {
  ActionIcon,
  Tooltip,
  Badge,
  Divider,
  HoverCard,
  Menu,
  Modal,
  Button,
  Text,
  Title,
  Stack,
  Group,
  Loader as MantineLoader,
  ScrollArea,
} from "@mantine/core";
import {
  IconCopy,
  IconPlayerPause,
  IconPlayerPlay,
  IconPlayerStop,
  IconDownload,
  IconCheck,
  IconDotsVertical,
  IconPencil,
  IconPhoto,
  IconTrash,
  IconFileText,
  IconSearch,
  IconPlus,
  IconVolume,
} from "@tabler/icons-react";

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
  readOnly?: boolean;

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
    readOnly = false,
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
      audioGeneratorOpened: false,
      confirmDeleteOpened: false,
    });
    const [isGeneratingSpeech, setIsGeneratingSpeech] = useState(false);
    const [agentSessions, setAgentSessions] = useState<TAgentSession[] | null>(null);

    const { t } = useTranslation();
    const isChatSpeechEnabled = useIsFeatureEnabled("chat-generate-speech");
    const isImageToolsEnabled = useIsFeatureEnabled("image-tools");

    const { agents, reactionTemplates, socket, userPreferences, agentTaskStatus } = useStore(
      (s) => ({
        agents: s.agents,
        reactionTemplates: s.reactionTemplates,
        socket: s.socket,
        userPreferences: s.userPreferences,
        agentTaskStatus: s.agentTaskStatus,
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
      if (!id || !versions?.length || type !== "assistant") return;

      getAgentSessionsForMessage(id)
        .then((sessions) => setAgentSessions(sessions))
        .catch(() => setAgentSessions(null));
    }, [id, versions?.length, type]);

    useEffect(() => {
      if (!id) return;

      socket.on(`audio-file-${id}`, (audioFile) => {
        setIsGeneratingSpeech(false);

        if (audioPlayer) {
          audioPlayer.stop();
          audioPlayer.destroy();
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
      setMessageState((prev) => ({ ...prev, confirmDeleteOpened: false }));
    };

    const finishEditing = () => {
      const newValue = textareaValueRef.current;

      if (!newValue) {
        toggleEditMode();
        return;
      }

      setInnerText(newValue);

      if (id && type === "assistant" && versions && newValue) {
        const newVersions = versions.map((v, vIdx) => {
          if (currentVersion === vIdx) {
            return { ...v, text: newValue };
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

    return (
      <div className={`message ${type === "user" ? "user" : "assistant"}`}>
        {isEditing && !readOnly ? (
          <MessageEditor
            textareaValueRef={textareaValueRef}
            text={versions?.[currentVersion]?.text || innerText}
            messageId={id}
            onImageGenerated={onImageGenerated}
          />
        ) : (
          <div>
            <MarkdownRenderer
              markdown={versions?.[currentVersion]?.text || innerText}
              extraClass={`message-text ${type === "user" ? "user" : "assistant"}`}
              attachments={attachments}
            />
          </div>
        )}

        {!id && type === "assistant" && (
          <Group gap="xs" mt="xs">
            <MantineLoader size="sm" color="violet" />
            <Text size="sm" c="dimmed">
              {agentTaskStatus || t("thinking...")}
            </Text>
          </Group>
        )}

        <section
          className={`message__attachments ${type === "user" ? "user" : ""}`}
        >
          {attachments &&
            attachments.map((attachment, aIdx) => {
              const src =
                attachment.content?.startsWith("data:") ||
                attachment.content?.startsWith("http")
                  ? attachment.content
                  : `${API_URL}${attachment.content?.startsWith("/") ? "" : "/"}${attachment.content || ""}`;
              return (
                <Thumbnail
                  {...attachment}
                  index={aIdx}
                  src={src}
                  key={aIdx}
                  message_id={id}
                />
              );
            })}
          {versions?.[currentVersion]?.sources &&
            versions[currentVersion].sources.length > 0 && (
              <Group gap="xs" mt="xs" wrap="wrap">
                {versions[currentVersion].sources.map((s, sIdx) => (
                  <Source key={sIdx} source={s} />
                ))}
              </Group>
            )}

          {versions?.[currentVersion]?.web_search_results &&
            versions?.[currentVersion]?.web_search_results.map(
              (result, rIdx) => {
                if (!result) return null;
                return (
                  <WebSearchResultInspector key={rIdx} result={result} />
                );
              }
            )}
        </section>

        {/* ── Action bar ── */}
        <div className="message-buttons">
          <Tooltip label={t("copy-to-clipboard")} withArrow>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="sm"
              onClick={copyToClipboard}
            >
              <IconCopy size={18} />
            </ActionIcon>
          </Tooltip>

          {id && !readOnly && (
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
                  initialPrompt={
                    versions?.[currentVersion]?.text || innerText
                  }
                />
              )}

              {audioPlayer && (
                <>
                  {isPlayingAudio ? (
                    <Tooltip label={t("pause-speech")} withArrow>
                      <ActionIcon
                        variant="subtle"
                        color="gray"
                        size="sm"
                        onClick={() => {
                          audioPlayer.pause();
                          setIsPlayingAudio(false);
                        }}
                      >
                        <IconPlayerPause size={18} />
                      </ActionIcon>
                    </Tooltip>
                  ) : (
                    <Tooltip label={t("play-speech")} withArrow>
                      <ActionIcon
                        variant="subtle"
                        color="gray"
                        size="sm"
                        onClick={() => {
                          audioPlayer.play();
                          setIsPlayingAudio(true);
                        }}
                      >
                        <IconPlayerPlay size={18} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                  <Tooltip label={t("stop-speech")} withArrow>
                    <ActionIcon
                      variant="subtle"
                      color="gray"
                      size="sm"
                      onClick={() => {
                        audioPlayer.stop();
                        setIsPlayingAudio(false);
                      }}
                    >
                      <IconPlayerStop size={18} />
                    </ActionIcon>
                  </Tooltip>
                  <Tooltip label={t("download-audio")} withArrow>
                    <ActionIcon
                      variant="subtle"
                      color="gray"
                      size="sm"
                      onClick={() => {
                        const filename = slugify(
                          versions?.[currentVersion]?.text || text
                        ).slice(0, 100);
                        audioPlayer.download(filename);
                      }}
                    >
                      <IconDownload size={18} />
                    </ActionIcon>
                  </Tooltip>
                </>
              )}

              {isEditing && (
                <Tooltip label={t("finish")} withArrow>
                  <ActionIcon
                    variant="filled"
                    color="violet"
                    size="sm"
                    onClick={finishEditing}
                  >
                    <IconCheck size={18} />
                  </ActionIcon>
                </Tooltip>
              )}

              <Reactions
                direction={type === "user" ? "right" : "left"}
                onReaction={handleReaction}
                messageId={id.toString()}
                currentReactions={
                  innerReactions?.map((r) => r.template) || []
                }
              />
            </>
          )}

          {/* Reaction emojis – show in both edit and read-only mode */}
          {id && innerReactions && innerReactions.length > 0 && (
            <Group gap={4} align="center">
              {innerReactions.map((r) => {
                const rt = reactionTemplates.find((rt) => rt.id === r.template);
                return rt ? (
                  <span key={`${r.id}-${r.template}`}>{rt.emoji}</span>
                ) : null;
              })}
            </Group>
          )}

          {/* Version selector (each badge shows agent + token info on hover) */}
          {versions && (
            <Group gap={4} align="center">
              {versions.map((v, vIdx) => (
                <HoverCard key={vIdx} width={200} shadow="md" withArrow>
                  <HoverCard.Target>
                    <Badge
                      variant={currentVersion === vIdx ? "filled" : "default"}
                      style={{ cursor: "pointer" }}
                      size="sm"
                      onClick={() => {
                        setCurrentVersion(vIdx);
                        setAudioPlayer(null);
                      }}
                    >
                      {vIdx + 1}
                    </Badge>
                  </HoverCard.Target>
                  <HoverCard.Dropdown>
                    <Stack gap="xs">
                      {v.agent_name && (
                        <>
                          <Text size="sm" fw={600} ta="center">
                            {v.agent_name}
                          </Text>
                          <Divider />
                        </>
                      )}
                      {agentSessions?.[vIdx] && (
                        <>
                          <Text size="xs">
                            <Text span c="dimmed">{t("iterations")}:</Text>{" "}
                            <strong>{agentSessions[vIdx].iterations}</strong>
                          </Text>
                          {agentSessions[vIdx].tool_calls_count > 0 && (
                            <Text size="xs">
                              <Text span c="dimmed">{t("tool-calls")}:</Text>{" "}
                              <strong>{agentSessions[vIdx].tool_calls_count}</strong>
                            </Text>
                          )}
                          {agentSessions[vIdx].total_duration != null && (
                            <Text size="xs">
                              <Text span c="dimmed">{t("duration")}:</Text>{" "}
                              <strong>{agentSessions[vIdx].total_duration!.toFixed(1)}s</strong>
                            </Text>
                          )}
                          {agentSessions[vIdx].model_slug && (
                            <Text size="xs">
                              <Text span c="dimmed">{t("model")}:</Text>{" "}
                              <strong>{agentSessions[vIdx].model_slug}</strong>
                            </Text>
                          )}
                        </>
                      )}
                      {v.usage && (
                        <>
                          <Text size="xs">
                            <Text span c="dimmed">Prompt:</Text>{" "}
                            <strong>{v.usage.prompt_tokens}</strong>
                          </Text>
                          <Text size="xs">
                            <Text span c="dimmed">Completion:</Text>{" "}
                            <strong>{v.usage.completion_tokens}</strong>
                          </Text>
                          <Text size="xs">
                            <Text span c="dimmed">Total:</Text>{" "}
                            <strong>{v.usage.total_tokens}</strong>
                          </Text>
                          {v.usage.model_slug && !agentSessions?.[vIdx]?.model_slug && (
                            <Text size="xs">
                              <Text span c="dimmed">{t("model")}:</Text>{" "}
                              <strong>{v.usage.model_slug}</strong>
                            </Text>
                          )}
                        </>
                      )}
                    </Stack>
                  </HoverCard.Dropdown>
                </HoverCard>
              ))}
            </Group>
          )}

          {/* Message options menu */}
          {id && !readOnly && (
            <Menu shadow="md" withArrow position="top-end">
              <Menu.Target>
                <ActionIcon variant="subtle" color="gray" size="sm">
                  <IconDotsVertical size={18} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
                {isChatSpeechEnabled && (
                  <Menu.Item
                    leftSection={<IconVolume size={16} />}
                    onClick={() =>
                      setMessageState((prev) => ({
                        ...prev,
                        audioGeneratorOpened: true,
                      }))
                    }
                  >
                    {t("generate-speech")}
                  </Menu.Item>
                )}
                <Menu.Item
                  leftSection={
                    isEditing ? (
                      <IconCheck size={16} />
                    ) : (
                      <IconPencil size={16} />
                    )
                  }
                  onClick={toggleEditMode}
                >
                  {isEditing ? t("finish") : t("edit")}
                </Menu.Item>
                {isImageToolsEnabled && (
                  <Menu.Item
                    leftSection={<IconPhoto size={16} />}
                    onClick={() =>
                      setMessageState((prev) => ({
                        ...prev,
                        imageGeneratorOpened: true,
                      }))
                    }
                  >
                    {t("generate-image")}
                  </Menu.Item>
                )}
                <Menu.Divider />
                <Menu.Item
                  color="red"
                  leftSection={<IconTrash size={16} />}
                  onClick={() =>
                    setMessageState((prev) => ({
                      ...prev,
                      confirmDeleteOpened: true,
                    }))
                  }
                >
                  {t("delete")}
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          )}
        </div>

        {/* AudioGenerator modal (externally triggered) */}
        {id && (
          <AudioGenerator
            text={versions?.[currentVersion]?.text || innerText}
            messageId={id.toString()}
            opened={messageState.audioGeneratorOpened}
            onClose={() =>
              setMessageState((prev) => ({
                ...prev,
                audioGeneratorOpened: false,
              }))
            }
          />
        )}

        {/* Delete confirmation modal */}
        <Modal
          opened={messageState.confirmDeleteOpened}
          onClose={() =>
            setMessageState((prev) => ({
              ...prev,
              confirmDeleteOpened: false,
            }))
          }
          title={t("delete-message")}
          centered
          size="sm"
        >
          <Stack gap="md">
            <Text size="sm">{t("im-sure")}?</Text>
            <Group justify="flex-end" gap="sm">
              <Button
                variant="default"
                size="sm"
                onClick={() =>
                  setMessageState((prev) => ({
                    ...prev,
                    confirmDeleteOpened: false,
                  }))
                }
              >
                {t("cancel")}
              </Button>
              <Button
                color="red"
                size="sm"
                leftSection={<IconTrash size={16} />}
                onClick={handleDelete}
              >
                {t("delete")}
              </Button>
            </Group>
          </Stack>
        </Modal>
      </div>
    );
  }
);

// ─── Source ────────────────────────────────────────────────────────────────────

const Source = ({ source }: { source: TSource }) => {
  const [isVisible, setIsVisible] = useState(false);
  const { t } = useTranslation();

  return (
    <>
      <Badge
        variant="outline"
        color="gray"
        size="lg"
        style={{ cursor: "pointer" }}
        leftSection={<IconFileText size={14} />}
        onClick={() => setIsVisible(true)}
      >
        {t(source.model_name)} {source.model_id}
      </Badge>

      <Modal
        opened={isVisible}
        onClose={() => setIsVisible(false)}
        title={
          <Group gap="xs">
            <IconFileText size={18} />
            <Text fw={600} size="sm">
              {t(source.model_name)} {source.model_id}
            </Text>
          </Group>
        }
        centered
        size="lg"
      >
        <Stack gap="md">
          {source.extra && (
            <Text size="xs" c="dimmed">
              {source.extra}
            </Text>
          )}
          <ScrollArea.Autosize mah={400}>
            <Text
              size="sm"
              style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", lineHeight: 1.6 }}
            >
              {source.content}
            </Text>
          </ScrollArea.Autosize>
        </Stack>
      </Modal>
    </>
  );
};

// ─── WebSearchResultInspector ─────────────────────────────────────────────────

const WebSearchResultInspector = ({ result }: { result: any }) => {
  const { t } = useTranslation();
  const [isVisible, setIsVisible] = useState(false);

  const handleOpenWebsite = () => {
    window.open(result.url, "_blank");
  };

  return (
    <div className="rounded-xl p-4 shadow-md" style={{ background: "var(--code-bg-color)", border: "1px solid var(--hovered-color)" }}>
      <p
        onClick={handleOpenWebsite}
        className="truncate cursor-pointer rounded-lg p-3 transition-all text-sm web-search-url"
        style={{ background: "var(--bg-secondary-color)", border: "1px solid var(--hovered-color)", color: "var(--font-color-secondary)" }}
        title={result.url}
      >
        {result.url}
      </p>
      <Button
        variant="default"
        size="xs"
        leftSection={<IconSearch size={16} />}
        onClick={() => setIsVisible(true)}
        mt="xs"
      >
        {t("inspect-content")}
      </Button>

      <Modal
        opened={isVisible}
        onClose={() => setIsVisible(false)}
        title={result.url}
        centered
        size="lg"
      >
        <Stack gap="md">
          <Title order={4} className="break-all">
            {result.url}
          </Title>
          <pre className="whitespace-pre-wrap break-all">{result.content}</pre>
        </Stack>
      </Modal>
    </div>
  );
};

// ─── MessageEditor ────────────────────────────────────────────────────────────

const MessageEditor = ({
  text,
  textareaValueRef,
  messageId,
  onImageGenerated,
}: {
  text: string;
  textareaValueRef: React.MutableRefObject<string | null>;
  messageId: number | undefined;
  onImageGenerated: (
    imageContentB64: string,
    imageName: string,
    message_id: number
  ) => void;
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
  const isChatSpeechEnabled = useIsFeatureEnabled("chat-generate-speech");
  const isImageToolsEnabled = useIsFeatureEnabled("image-tools");

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        textareaRef.current.scrollHeight + "px";
    }
  }, [innerText]);

  const handleMouseUp = (e: React.MouseEvent<HTMLTextAreaElement>) => {
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
        className="w-full px-4 py-3 font-sans rounded-xl text-base leading-6 scrollbar-none resize-none focus:outline-none"
        style={{ background: "var(--code-bg-color)", color: "var(--font-color)", border: "1px solid var(--highlighted-color-opaque)" }}
        onChange={(e) => {
          textareaValueRef.current = e.target.value;
          setInnerText(e.target.value);
        }}
        defaultValue={text}
        onMouseUp={handleMouseUp}
        onTouchEnd={handleTouchEnd}
      />
      {editionOptions.isVisible &&
        (isImageToolsEnabled || isChatSpeechEnabled) &&
        createPortal(
          <div
            style={{
              top: editionOptions.top,
              left: editionOptions.left,
              background: "var(--modal-bg-color)",
              border: "1px solid var(--hovered-color)",
              boxShadow: "0 8px 24px rgba(0,0,0,0.3)",
            }}
            className="absolute w-fit rounded-xl p-3 z-50"
          >
            {editionOptions.generateImage && messageId && (
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
            <Stack gap="xs">
              {isImageToolsEnabled && (
                <Button
                  variant="default"
                  size="xs"
                  leftSection={<IconPhoto size={16} />}
                  onClick={generateImageWithThisText}
                  fullWidth
                >
                  {t("generate-image")}
                </Button>
              )}
              {isChatSpeechEnabled && (
                <AudioGenerator
                  text={editionOptions.currentText}
                  messageId={messageId?.toString() ?? ""}
                />
              )}
            </Stack>
          </div>,
          document.body
        )}
    </div>
  );
};

