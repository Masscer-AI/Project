import React, { useCallback, useEffect, useRef, useState } from "react";
import { Message } from "../../components/Message/Message";
import { ChatInput } from "../../components/ChatInput/ChatInput";

import { useLoaderData, useLocation, useNavigate, useRevalidator } from "react-router-dom";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { TChatLoader, TMessage } from "../../types/chatTypes";
import { ChatHeader } from "../../components/ChatHeader/ChatHeader";
import toast from "react-hot-toast";

import { useTranslation } from "react-i18next";
import { TVersion } from "../../types";
import { ConversationHeaderActions } from "../../components/ConversationActions/ConversationHeaderActions";
import { ActionIcon } from "@mantine/core";
import { IconArrowDown } from "@tabler/icons-react";
import {
  linkMessageAttachment,
  triggerAgentTask,
  triggerPlatformAssistantTask,
  triggerComplianceAssistantTask,
  isPlatformAssistant,
  isComplianceAssistant,
  buildClientDatetimePayload,
  uploadMessageAttachments,
  sendHumanMessageToConversation,
} from "../../modules/apiCalls";
import { HumanTakeoverBanner } from "../../components/HumanTakeoverBanner/HumanTakeoverBanner";
import type { TConversation } from "../../types";
import { agentsInChatSelectionOrder } from "../../modules/agentSelection";
import { useAgentSelectionPrompt } from "../../hooks/useAgentSelectionPrompt";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import { playNotificationSound } from "../../utils/notificationSound";

const complianceKickoffsStarted = new Set<string>();

export default function ChatView() {
  const loaderData = useLoaderData() as TChatLoader;

  const {
    chatState,
    conversation,
    cleanAttachments,
    socket,
    setUser,
    agents,
    startup,
    userPreferences,
    hydrateConversation,
    setConversation,
    setSpecifiedUrls,
    setAgentTaskStatus,
    setChatSelectedAgentSlugs,
  } = useStore((state) => ({
    socket: state.socket,
    chatState: state.chatState,
    conversation: state.conversation,
    cleanAttachments: state.cleanAttachments,
    modelsAndAgents: state.modelsAndAgents,
    setUser: state.setUser,
    agents: state.agents,
    startup: state.startup,
    userPreferences: state.userPreferences,
    hydrateConversation: state.hydrateConversation,
    setConversation: state.setConversation,
    setSpecifiedUrls: state.setSpecifiedUrls,
    setAgentTaskStatus: state.setAgentTaskStatus,
    setChatSelectedAgentSlugs: state.setChatSelectedAgentSlugs,
  }));

  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const revalidator = useRevalidator();

  const routeConversation = loaderData.conversation;
  const isComplianceRoute = location.pathname === "/compliance";
  const activeConversation =
    conversation &&
    (conversation.id === routeConversation?.id ||
      (isComplianceRoute && conversation.metadata?.surface === "compliance"))
      ? conversation
      : routeConversation;
  const conversationId = activeConversation.id;
  const isComplianceSurface =
    isComplianceRoute ||
    activeConversation?.metadata?.surface === "compliance";
  const isForeignConversation =
    activeConversation?.user_id != null &&
    loaderData.user?.id != null &&
    activeConversation.user_id !== loaderData.user.id;
  const isWidgetConversation = activeConversation?.chat_widget_id != null;
  const isWhatsappConversation = Boolean(activeConversation?.whatsapp_user_number);
  const isViewerBase =
    isForeignConversation || isWidgetConversation || isWhatsappConversation;
  const canReplaceAgent =
    useIsFeatureEnabled("can-replace-agent-in-conversations") === true;
  const canEditConversationData =
    useIsFeatureEnabled("can-edit-conversation-data") === true;
  const activeTakeover = activeConversation?.active_takeover;
  const isTakeoverOperator =
    activeTakeover?.status === "ACTIVE" &&
    activeTakeover.operator_user_id === loaderData.user?.id;
  const isViewer = isViewerBase && !isTakeoverOperator;
  const canTakeOver =
    canReplaceAgent &&
    isViewerBase &&
    !isTakeoverOperator &&
    activeTakeover?.status !== "ACTIVE";
  const composerMode: "agent" | "human" | "readonly" = isTakeoverOperator
    ? "human"
    : isViewer
      ? "readonly"
      : "agent";

  const chatMessageContainerRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<number | null>(null);
  const [showScrollToEnd, setShowScrollToEnd] = useState(false);

  useEffect(() => {
    setUser(loaderData.user);
    startup();
  }, [loaderData.user, startup]);

  const [messages, setMessages] = useState<TMessage[]>(
    () => loaderData.conversation?.messages ?? []
  );

  const isMultiAgentEnabled = useIsFeatureEnabled("multi-agent-chat") === true;
  const agentsModal = useAgentSelectionPrompt({
    conversationId,
    enabled: !isViewer && !isComplianceSurface,
    hasAgents: agents.length > 0,
    selectedAgentCount: chatState.selectedAgents.length,
    messageCount: messages.length,
    closeOnFirstSelection: !isMultiAgentEnabled,
  });

  useEffect(() => {
    if (!isComplianceSurface) return;
    const compliance = agents.find(isComplianceAssistant);
    if (!compliance) return;
    if (
      chatState.selectedAgents.length !== 1 ||
      chatState.selectedAgents[0] !== compliance.slug
    ) {
      setChatSelectedAgentSlugs([compliance.slug]);
    }
  }, [
    isComplianceSurface,
    agents,
    chatState.selectedAgents,
    setChatSelectedAgentSlugs,
  ]);

  useEffect(() => {
    hydrateConversation(loaderData.conversation);
  }, [loaderData.conversation.id, hydrateConversation]);

  useEffect(() => {
    const handleAgentEvents = (raw: {
      user_id?: number;
      message?: { type: string; conversation_id?: string; version?: TVersion };
    }) => {
      const data = raw?.message;
      const convId = conversationId;
      if (!data || !convId || data.conversation_id !== convId) return;
      if (data.type === "agent_version_ready" && data.version) {
        console.debug(
          "[agent-task] agent_version_ready (does not clear stop)",
          {
            conversation_id: data.conversation_id,
            agent_slug: data.version.agent_slug,
            agentTaskStatus: useStore.getState().agentTaskStatus,
            agentTaskConversationId:
              useStore.getState().agentTaskConversationId,
          }
        );
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (!last || last.type !== "assistant") return prev;
          const versions = [...(last.versions || [])];
          const existingIdx = versions.findIndex(
            (v) => v.agent_slug === data.version!.agent_slug
          );
          if (existingIdx >= 0) versions[existingIdx] = data.version!;
          else versions.push(data.version!);
          const updated = [...prev];
          updated[updated.length - 1] = { ...last, versions, text: versions[0]?.text ?? last.text };
          return updated;
        });
      }
    };

    socket.on("agent_events_channel", handleAgentEvents);

    return () => {
      socket.off("agent_events_channel", handleAgentEvents);
    };
  }, [conversationId, socket]);

  const scrollChat = () => {
    const container = chatMessageContainerRef.current;
    if (!container) return;
    const start = container.scrollTop;
    const end = container.scrollHeight;
    const duration = 1000;
    const startTime = performance.now();

    const smoothScroll = (currentTime: number) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const ease =
        progress < 0.5
          ? 2 * progress * progress
          : -1 + (4 - 2 * progress) * progress;

      container.scrollTop = start + (end - start) * ease;

      if (elapsed < duration) {
        requestAnimationFrame(smoothScroll);
      } else {
        timeoutRef.current = null;
      }
    };

    requestAnimationFrame(smoothScroll);
  };

  const updateScrollToEndVisibility = useCallback(() => {
    const container = chatMessageContainerRef.current;
    if (!container) return;
    const remaining =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    setShowScrollToEnd(remaining > 60);
  }, []);

  useEffect(() => {
    if (!conversation?.messages) return;
    const { agentTaskStatus, agentTaskConversationId } = useStore.getState();
    if (
      agentTaskStatus &&
      agentTaskConversationId === conversation.id &&
      conversation.messages.length === 0
    ) {
      return;
    }
    setMessages(conversation.messages);
  }, [conversation]);

  useEffect(() => {
    const container = chatMessageContainerRef.current;
    if (!container) return;
    updateScrollToEndVisibility();
    const onScroll = () => updateScrollToEndVisibility();
    container.addEventListener("scroll", onScroll);
    return () => {
      container.removeEventListener("scroll", onScroll);
    };
  }, [updateScrollToEndVisibility]);

  useEffect(() => {
    updateScrollToEndVisibility();
  }, [messages.length, updateScrollToEndVisibility]);

  useEffect(() => {
    if (isViewer) return;
    if (
      loaderData.query &&
      agents.length > 0 &&
      messages.length === 0 &&
      loaderData.sendQuery &&
      chatState.selectedAgents.length > 0
    ) {
      handleSendMessage(loaderData.query);
    }
  }, [
    loaderData.query,
    agents,
    chatState.selectedAgents.length,
    isViewer,
    loaderData.sendQuery,
    messages.length,
  ]);

  const handleHumanSendMessage = async (input: string) => {
    if (!conversationId) {
      toast.error("No conversation found");
      return false;
    }

    const fileUploads = chatState.attachments.filter(
      (a) => typeof a.content === "string" && a.content.startsWith("data:")
    );
    const existingDocs = chatState.attachments.filter(
      (a) =>
        !(typeof a.content === "string" && a.content.startsWith("data:")) &&
        a.id != null
    );
    const unsupported = chatState.attachments.filter(
      (a) =>
        !(typeof a.content === "string" && a.content.startsWith("data:")) &&
        a.id == null
    );
    if (unsupported.length > 0) {
      toast.error(t("human-takeover-unsupported-attachment"));
      return false;
    }

    let attachmentIds: string[] = [];
    if (fileUploads.length > 0) {
      const uploadRes = await uploadMessageAttachments(
        conversationId,
        fileUploads.map((a) => ({
          content: a.content,
          name: a.name || "file",
        }))
      );
      attachmentIds = uploadRes.attachments.map((att: { id: string }) => att.id);
    }

    for (const doc of existingDocs) {
      const docId =
        typeof doc.id === "number" ? doc.id : parseInt(String(doc.id), 10);
      if (isNaN(docId)) continue;
      const linkRes = await linkMessageAttachment(conversationId, {
        kind: "rag_document",
        rag_document_id: docId,
      });
      attachmentIds.push(linkRes.attachment.id);
    }

    const trimmed = input.trim();
    if (!trimmed && attachmentIds.length === 0) return false;

    const optimistic: TMessage = {
      type: "assistant",
      text: trimmed,
      attachments: chatState.attachments,
    };
    setMessages((prev) => [...prev, optimistic]);

    try {
      await sendHumanMessageToConversation(
        conversationId,
        trimmed,
        attachmentIds
      );
      await setConversation(conversationId);
      cleanAttachments();
      setSpecifiedUrls([]);
      scrollChat();
      return true;
    } catch (error) {
      console.error("Error sending human message:", error);
      toast.error(t("human-takeover-send-failed"));
      setMessages((prev) => {
        const last = prev[prev.length - 1];
        if (last?.type === "assistant" && !last.id && last.text === trimmed) {
          return prev.slice(0, -1);
        }
        return prev;
      });
      return false;
    }
  };

  const handleSendMessage = async (input: string) => {
    if (input.trim() === "") return false;

    if (composerMode === "human") {
      return handleHumanSendMessage(input);
    }

    if (chatState.writtingMode) return false;

    let selectedAgents = agentsInChatSelectionOrder(agents, chatState.selectedAgents);
    if (selectedAgents.length === 0) {
      playNotificationSound("error");
      toast.error(t("select-at-least-one-agent-to-chat"));
      return false;
    }

    const assistantMessage: TMessage = {
      type: "assistant",
      text: "",
      attachments: [],
      agent_slug: selectedAgents[0].slug,
    };

    setMessages((prev) => {
      const userMessage: TMessage = {
        type: "user",
        text: input,
        attachments: chatState.attachments,
        index: prev.length,
      };
      return [...prev, userMessage, assistantMessage];
    });
    setAgentTaskStatus(t("agent-preparing-request"), conversationId ?? null);

    const revertOptimisticSend = () => {
      setAgentTaskStatus(null);
      setMessages((prev) => {
        if (prev.length < 2) return prev;
        const last = prev[prev.length - 1];
        const before = prev[prev.length - 2];
        if (last?.type === "assistant" && !last.id && before?.type === "user") {
          return prev.slice(0, -2);
        }
        return prev;
      });
    };

    try {
      if (!conversationId) {
        toast.error("No conversation found");
        revertOptimisticSend();
        return false;
      }

      type UserInput =
        | { type: "input_text"; text: string }
        | { type: "input_attachment"; attachment_id: string };
      const userInputs: UserInput[] = [{ type: "input_text", text: input }];

      if (chatState.attachments.length > 0) {
        const fileUploads = chatState.attachments.filter(
          (a) => typeof a.content === "string" && a.content.startsWith("data:")
        );
        const ragDocs = chatState.attachments.filter(
          (a) =>
            !(typeof a.content === "string" && a.content.startsWith("data:")) &&
            a.id != null
        );

        const toUpload = fileUploads.map((a) => ({
          content: a.content,
          name: a.name || "file",
        }));

        if (toUpload.length > 0) {
          const uploadRes = await uploadMessageAttachments(
            conversationId,
            toUpload
          );
          for (const att of uploadRes.attachments) {
            userInputs.push({ type: "input_attachment", attachment_id: att.id });
          }
        }

        for (const rag of ragDocs) {
          const docId = typeof rag.id === "number" ? rag.id : parseInt(String(rag.id), 10);
          if (!isNaN(docId)) {
            const linkRes = await linkMessageAttachment(conversationId, {
              kind: "rag_document",
              rag_document_id: docId,
            });
            userInputs.push({ type: "input_attachment", attachment_id: linkRes.attachment.id });
          }
        }
      }

      const specifiedUrls = chatState.specifiedUrls || [];
      if (specifiedUrls.length > 0) {
        const uiWebsiteAttachments: any[] = [];
        for (const item of specifiedUrls) {
          const url = (item as any)?.url;
          if (!url) continue;
          const linkRes = await linkMessageAttachment(conversationId, {
            kind: "website",
            url,
          });
          userInputs.push({
            type: "input_attachment",
            attachment_id: linkRes.attachment.id,
          });
          uiWebsiteAttachments.push({
            type: "website",
            content: url,
            name: (linkRes.attachment as any)?.url || url,
          });
        }

        if (uiWebsiteAttachments.length > 0) {
          setMessages((prev) => {
            const updated = [...prev];
            const userIdx = updated.length - 2;
            const target = updated[userIdx];
            if (!target || target.type !== "user") return prev;
            updated[userIdx] = {
              ...target,
              attachments: [...(target.attachments || []), ...uiWebsiteAttachments],
            };
            return updated;
          });
        }
      }

      const isPlatform =
        selectedAgents.length === 1 && isPlatformAssistant(selectedAgents[0]);
      const isCompliance =
        selectedAgents.length === 1 && isComplianceAssistant(selectedAgents[0]);
      const taskRes = isPlatform
        ? await triggerPlatformAssistantTask({
            conversation_id: conversationId,
            agent_slug: selectedAgents[0].slug,
            user_inputs: userInputs,
            client_datetime: buildClientDatetimePayload(),
          })
        : isCompliance
          ? await triggerComplianceAssistantTask({
              conversation_id: conversationId,
              agent_slug: selectedAgents[0].slug,
              user_inputs: userInputs,
              client_datetime: buildClientDatetimePayload(),
            })
        : await triggerAgentTask({
            conversation_id: conversationId,
            agent_slugs: selectedAgents.map((a) => a.slug),
            user_inputs: userInputs,
            multiagentic_modality: userPreferences.multiagentic_modality,
            client_datetime: buildClientDatetimePayload(),
          });

      if (taskRes.agent_skipped && taskRes.takeover) {
        console.debug("[agent-task] trigger skipped (takeover) → clear stop", {
          conversationId: conversationId,
        });
        setAgentTaskStatus(null);
        await setConversation(conversationId);
      }

      cleanAttachments();
      setSpecifiedUrls([]);
      scrollChat();
      return true;
    } catch (error) {
      console.error("Error triggering agent task:", error);
      toast.error(t("agent-task-failed"));
      console.debug("[agent-task] trigger failed → clear stop", {
        conversationId,
        error,
      });
      revertOptimisticSend();
      return false;
    }
  };

  useEffect(() => {
    if (!isComplianceSurface || isViewer || composerMode !== "agent") return;
    if (!conversationId || messages.length > 0) return;
    if (chatState.writtingMode) return;
    const compliance = agents.find(isComplianceAssistant);
    if (!compliance) return;
    if (
      chatState.selectedAgents.length !== 1 ||
      chatState.selectedAgents[0] !== compliance.slug
    ) {
      return;
    }
    if (complianceKickoffsStarted.has(conversationId)) return;
    complianceKickoffsStarted.add(conversationId);
    void handleSendMessage(t("compliance-kickoff-message")).then((ok) => {
      if (!ok) complianceKickoffsStarted.delete(conversationId);
    });
  }, [
    isComplianceSurface,
    isViewer,
    composerMode,
    conversationId,
    messages.length,
    agents,
    chatState.selectedAgents,
    chatState.writtingMode,
    t,
  ]);

  const onImageGenerated = useCallback(
    (imageContentB64: string, imageName: string, message_id: number) => {
      setMessages((prevMessages) => {
        const messageIndex = prevMessages.findIndex((m) => m.id === message_id);
        if (messageIndex === -1) return prevMessages;

        const copyMessages = [...prevMessages];
        copyMessages[messageIndex] = {
          ...copyMessages[messageIndex],
          attachments: [
            ...(copyMessages[messageIndex].attachments || []),
            {
              type: "image",
              content: imageContentB64,
              name: imageName,
              file: null,
              text: "",
            },
          ],
        };
        return copyMessages;
      });
    },
    []
  );

  const handleRegenerateAgentTask = useCallback(
    async (index: number, newText: string) => {
      if (!conversationId) return;

      let selectedAgents = agentsInChatSelectionOrder(agents, chatState.selectedAgents);
      if (selectedAgents.length === 0) {
        playNotificationSound("error");
        toast.error(t("select-at-least-one-agent-to-chat"));
        return;
      }

      const regenPayload = { userId: null as number | null };
      const assistantMessage: TMessage = {
        type: "assistant",
        text: "",
        attachments: [],
        agent_slug: selectedAgents[0].slug,
      };

      setMessages((prev) => {
        const userMessage = prev[index];
        if (!userMessage?.id || userMessage.type !== "user") return prev;
        regenPayload.userId = userMessage.id;
        const base = prev.slice(0, index + 1).map((m, i) =>
          i === index ? { ...m, text: newText } : m
        );
        return [...base, assistantMessage];
      });

      if (!regenPayload.userId) return;

      setAgentTaskStatus(t("agent-preparing-request"), conversationId);

      try {
        const isPlatform =
          selectedAgents.length === 1 && isPlatformAssistant(selectedAgents[0]);
        const isCompliance =
          selectedAgents.length === 1 && isComplianceAssistant(selectedAgents[0]);
        const taskRes = isPlatform
          ? await triggerPlatformAssistantTask({
              conversation_id: conversationId,
              agent_slug: selectedAgents[0].slug,
              user_inputs: [{ type: "input_text", text: newText }],
              regenerate_message_id: regenPayload.userId,
              client_datetime: buildClientDatetimePayload(),
            })
          : isCompliance
            ? await triggerComplianceAssistantTask({
                conversation_id: conversationId,
                agent_slug: selectedAgents[0].slug,
                user_inputs: [{ type: "input_text", text: newText }],
                regenerate_message_id: regenPayload.userId,
                client_datetime: buildClientDatetimePayload(),
              })
          : await triggerAgentTask({
              conversation_id: conversationId,
              agent_slugs: selectedAgents.map((a) => a.slug),
              user_inputs: [{ type: "input_text", text: newText }],
              multiagentic_modality: userPreferences.multiagentic_modality,
              regenerate_message_id: regenPayload.userId,
              client_datetime: buildClientDatetimePayload(),
            });

        if (taskRes.agent_skipped && taskRes.takeover) {
          console.debug(
            "[agent-task] regenerate skipped (takeover) → clear stop",
            { conversationId: conversationId }
          );
          setAgentTaskStatus(null);
          await setConversation(conversationId);
        }

        scrollChat();
      } catch (error) {
        console.error("Error regenerating via agent task:", error);
        toast.error(t("agent-task-failed"));
        console.debug("[agent-task] regenerate failed → clear stop", {
          conversationId: conversationId,
          error,
        });
        setAgentTaskStatus(null);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.type === "assistant" && !last.id) return prev.slice(0, -1);
          return prev;
        });
        void setConversation(conversationId);
      }
    },
    [
      agents,
      chatState,
      conversationId,
      setAgentTaskStatus,
      setConversation,
      t,
      userPreferences.multiagentic_modality,
    ]
  );

  const onMessageEdit = useCallback(
    (index: number, text: string, versions?: TVersion[]) => {
      if (versions !== undefined) {
        setMessages((prev) => {
          const message = prev[index];
          if (!message || message.type !== "assistant") return prev;
          const updated = [...prev];
          updated[index] = { ...updated[index], versions };
          return updated;
        });
        return;
      }
      void handleRegenerateAgentTask(index, text);
    },
    [handleRegenerateAgentTask]
  );

  const onMessageDeleted = useCallback((index: number) => {
    setMessages((prev) => prev.filter((_, i) => i !== index));
  }, []);

  return (
    <main className="flex relative h-screen w-full overflow-hidden" style={{ backgroundColor: "var(--bg-color)" }}>
      {userPreferences.background_image_source && (
        <img
          style={{ opacity: userPreferences.background_image_opacity }}
          className="absolute inset-0 w-full h-full object-cover rounded-lg z-0"
          src={userPreferences.background_image_source}
        />
      )}
      {chatState.isSidebarOpened && <Sidebar />}
      <div className="flex min-h-0 flex-col h-screen w-full md:mx-auto md:max-w-[900px] relative z-10 px-0 md:px-4 py-0 md:py-6 overflow-visible">
        <ChatHeader
          hideAgents={isComplianceSurface}
          onComplianceRestarted={(conv) => {
            hydrateConversation(conv);
            setMessages(conv.messages ?? []);
            setAgentTaskStatus(null);
            window.dispatchEvent(new Event("conversations-changed"));
            revalidator.revalidate();
          }}
          agentsModal={{
            opened: agentsModal.opened,
            onOpen: agentsModal.open,
            onClose: agentsModal.close,
          }}
          right={
            <ConversationHeaderActions
              conversation={activeConversation}
              readOnly={isViewer && !canEditConversationData}
              showActions={!isForeignConversation && !isComplianceSurface}
              onDeleted={() => {
                setConversation(null);
                navigate(isComplianceSurface ? "/compliance" : "/chat");
                window.dispatchEvent(new Event("conversations-changed"));
              }}
            />
          }
        />

        {(canTakeOver || isTakeoverOperator || activeTakeover) && (
          <HumanTakeoverBanner
            conversationId={activeConversation.id}
            activeTakeover={activeTakeover}
            canTakeOver={canTakeOver}
            isTakeoverOperator={isTakeoverOperator}
            onConversationUpdated={(conv) => {
              hydrateConversation(conv);
              setMessages(conv.messages ?? []);
            }}
          />
        )}

        <div
          ref={chatMessageContainerRef}
          className="min-h-0 flex-1 overflow-y-auto flex flex-col w-full pb-6 mt-6 px-1 md:px-2"
        >
          {messages &&
            messages.map((msg, index) => (
              <Message
                {...msg}
                key={msg.id ?? `tmp-${index}`}
                index={index}
                onImageGenerated={onImageGenerated}
                onMessageEdit={onMessageEdit}
                onMessageDeleted={onMessageDeleted}
                numberMessages={messages.length}
                readOnly={isViewer}
              />
            ))}
        </div>
        {showScrollToEnd && (
          <ActionIcon
            onClick={scrollChat}
            variant="default"
            radius="xl"
            size="lg"
            style={{ position: "absolute", right: 16, bottom: 140, zIndex: 10 }}
            className="!bg-white/10 !border-white/10 backdrop-blur shadow-lg hover:!bg-white/20"
            aria-label={t("scroll-to-end")}
          >
            <IconArrowDown size={18} />
          </ActionIcon>
        )}
        <div className="shrink-0 min-w-0 w-full">
          <ChatInput
            handleSendMessage={handleSendMessage}
            initialInput={
              loaderData.query && !loaderData.sendQuery ? loaderData.query : ""
            }
            composerMode={composerMode}
            readOnly={isViewer}
            readOnlyMessage={
              isWhatsappConversation && composerMode === "readonly"
                ? t("view-only-mode-whatsapp")
                : undefined
            }
          />
        </div>
      </div>
    </main>
  );
}
