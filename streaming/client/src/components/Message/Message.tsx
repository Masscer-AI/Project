import React, { useEffect, useRef, useState, memo } from "react";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import {
  TAttachment,
  TAgentSession,
  TAgentSessionExecutionLog,
  TAgentSessionToolCall,
  TSource,
  TVersion,
} from "../../types";
import { API_URL } from "../../modules/constants";
import { Thumbnail } from "../Thumbnail/Thumbnail";
import toast from "react-hot-toast";
import {
  deleteMessage,
  updateMessage,
  getAgentSessionsForMessage,
  getAgentSessionExecutionLogForMessage,
} from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { useStore } from "../../modules/store";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { Reactions } from "../Reactions/Reactions";

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
  IconCheck,
  IconDotsVertical,
  IconPencil,
  IconTrash,
  IconFileText,
  IconSearch,
} from "@tabler/icons-react";

type TReaction = {
  id: number;
  template: number;
};

interface Link {
  url: string;
  text: string;
}

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
    readOnly = false,
  }: MessageProps) => {
    const [isEditing, setIsEditing] = useState(false);
    const [innerText, setInnerText] = useState(text);
    const textareaValueRef = useRef<string | null>(null);
    const [currentVersion, setCurrentVersion] = useState(0);
    const [innerReactions, setInnerReactions] = useState(
      reactions || ([] as TReaction[])
    );
    const [messageState, setMessageState] = useState({
      confirmDeleteOpened: false,
      executionLogOpened: false,
    });
    const [agentSessions, setAgentSessions] = useState<TAgentSession[] | null>(null);
    const [executionLog, setExecutionLog] = useState<TAgentSessionExecutionLog[] | null>(null);
    const [executionLogLoading, setExecutionLogLoading] = useState(false);
    const [executionLogError, setExecutionLogError] = useState<string | null>(null);

    const { t } = useTranslation();
    const canEditConversationData =
      useIsFeatureEnabled("can-edit-conversation-data") === true;

    const { reactionTemplates, agentTaskStatus } = useStore(
      (s) => ({
        reactionTemplates: s.reactionTemplates,
        agentTaskStatus: s.agentTaskStatus,
      })
    );
    const canShowExecutionLog =
      Boolean(id) && type === "assistant" && Boolean(versions?.length);

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
      if (!id || !versions?.length || type !== "assistant") return;

      getAgentSessionsForMessage(id)
        .then((sessions) => setAgentSessions(sessions))
        .catch(() => setAgentSessions(null));
    }, [id, versions?.length, type]);

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

    const handleOpenExecutionLog = async () => {
      if (!id || !canShowExecutionLog) return;

      if (executionLog) {
        setMessageState((prev) => ({ ...prev, executionLogOpened: true }));
        return;
      }

      setExecutionLogLoading(true);
      setExecutionLogError(null);

      try {
        const response = await getAgentSessionExecutionLogForMessage(id);
        setExecutionLog(response.sessions);
      } catch (error) {
        console.error("Error loading execution log:", error);
        setExecutionLogError("Unable to load the execution log right now.");
      } finally {
        setExecutionLogLoading(false);
        setMessageState((prev) => ({ ...prev, executionLogOpened: true }));
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

          {canShowExecutionLog && (
            <Tooltip label="Execution log" withArrow>
              <Button
                variant="subtle"
                color="gray"
                size="xs"
                leftSection={
                  executionLogLoading ? (
                    <MantineLoader size={14} color="gray" />
                  ) : (
                    <IconFileText size={16} />
                  )
                }
                onClick={handleOpenExecutionLog}
                disabled={executionLogLoading}
              >
                Execution log
              </Button>
            </Tooltip>
          )}

          {/* Message options menu */}
          {id && !readOnly && canEditConversationData && (
            <Menu shadow="md" withArrow position="top-end">
              <Menu.Target>
                <ActionIcon variant="subtle" color="gray" size="sm">
                  <IconDotsVertical size={18} />
                </ActionIcon>
              </Menu.Target>
              <Menu.Dropdown>
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

        {/* Delete confirmation modal */}
        {canEditConversationData && (
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
        )}

        <ExecutionLogModal
          opened={messageState.executionLogOpened}
          onClose={() =>
            setMessageState((prev) => ({
              ...prev,
              executionLogOpened: false,
            }))
          }
          sessions={executionLog}
          loading={executionLogLoading}
          error={executionLogError}
          currentVersion={currentVersion}
        />
      </div>
    );
  }
);

const formatExecutionLogValue = (value: unknown) => {
  if (value == null) return "";
  if (typeof value === "string") return value;
  try {
    return JSON.stringify(value, null, 2);
  } catch (error) {
    console.error("Error stringifying execution log value:", error);
    return String(value);
  }
};

const ExecutionLogToolCall = ({ toolCall }: { toolCall: TAgentSessionToolCall }) => {
  return (
    <div
      className="rounded-xl px-4 py-3"
      style={{
        background: "var(--bg-color)",
        border: "1px solid var(--hovered-color)",
      }}
    >
      <Group justify="space-between" align="flex-start" wrap="wrap" gap="sm">
        <div>
          <Text fw={600} size="sm">
            #{toolCall.order} {toolCall.tool_name}
          </Text>
          {toolCall.iteration != null && (
            <Text size="xs" c="dimmed">
              Iteration {toolCall.iteration}
            </Text>
          )}
        </div>
        {toolCall.error ? (
          <Badge color="red" variant="light">
            Error
          </Badge>
        ) : (
          <Badge color="gray" variant="light">
            Completed
          </Badge>
        )}
      </Group>

      {toolCall.result_preview && (
        <Text
          size="sm"
          mt="sm"
          c="dimmed"
          style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", lineHeight: 1.5 }}
        >
          {toolCall.result_preview}
        </Text>
      )}

      <Stack gap="xs" mt="md">
        <details>
          <summary style={{ cursor: "pointer", fontWeight: 500 }}>Result</summary>
          <pre
            className="whitespace-pre-wrap break-all mt-3 rounded-lg p-3"
            style={{
              background: "var(--code-bg-color)",
              border: "1px solid var(--hovered-color)",
              fontSize: "0.9rem",
              lineHeight: 1.55,
            }}
          >
            {formatExecutionLogValue(toolCall.result)}
          </pre>
        </details>
      </Stack>
    </div>
  );
};

const ExecutionLogModal = ({
  opened,
  onClose,
  sessions,
  loading,
  error,
  currentVersion,
}: {
  opened: boolean;
  onClose: () => void;
  sessions: TAgentSessionExecutionLog[] | null;
  loading: boolean;
  error: string | null;
  currentVersion: number;
}) => {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title="Execution log"
      centered
      size="xl"
    >
      <Stack gap="md">
        {loading && (
          <Group gap="xs">
            <MantineLoader size="sm" color="violet" />
            <Text size="sm" c="dimmed">
              Loading execution log...
            </Text>
          </Group>
        )}

        {!loading && error && (
          <Text size="sm" c="red">
            {error}
          </Text>
        )}

        {!loading && !error && (!sessions || sessions.length === 0) && (
          <Text size="sm" c="dimmed">
            No agent session details were found for this message.
          </Text>
        )}

        {!loading && !error && sessions && sessions.length > 0 && (
          <ScrollArea.Autosize mah={500}>
            <Stack gap="md">
              {sessions.map((session, sessionIdx) => {
                const isCurrentVersion = currentVersion === sessionIdx;
                return (
                  <div
                    key={session.session_id}
                    className="rounded-xl p-4"
                    style={{
                      border: `1px solid ${isCurrentVersion ? "var(--highlighted-color-opaque)" : "var(--hovered-color)"}`,
                      background: "var(--code-bg-color)",
                    }}
                  >
                    <Stack gap="sm">
                      <Group justify="space-between" align="center" wrap="wrap">
                        <div>
                          <Text fw={600}>
                            {session.agent_slug || `Agent ${session.agent_index + 1}`}
                          </Text>
                          <Text size="xs" c="dimmed">
                            Version {session.agent_index + 1}
                            {session.model_slug ? ` • ${session.model_slug}` : ""}
                            {session.total_duration != null
                              ? ` • ${session.total_duration.toFixed(1)}s`
                              : ""}
                          </Text>
                        </div>
                      </Group>

                      {session.tool_calls.length === 0 ? (
                        <Text size="sm" c="dimmed">
                          No tools were used in this agent session.
                        </Text>
                      ) : (
                        <Stack gap="sm">
                          {session.tool_calls.map((toolCall) => (
                            <ExecutionLogToolCall
                              key={`${session.session_id}-${toolCall.call_id}-${toolCall.order}`}
                              toolCall={toolCall}
                            />
                          ))}
                        </Stack>
                      )}
                    </Stack>
                  </div>
                );
              })}
            </Stack>
          </ScrollArea.Autosize>
        )}
      </Stack>
    </Modal>
  );
};

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
}: {
  text: string;
  textareaValueRef: React.MutableRefObject<string | null>;
  messageId?: number;
  onImageGenerated?: (
    imageContentB64: string,
    imageName: string,
    message_id: number
  ) => void;
}) => {
  const [innerText, setInnerText] = useState(text);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height =
        textareaRef.current.scrollHeight + "px";
    }
  }, [innerText]);

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
      />
    </div>
  );
};

