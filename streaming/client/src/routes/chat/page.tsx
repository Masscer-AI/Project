import React, { useCallback, useEffect, useRef, useState } from "react";
import { Message } from "../../components/Message/Message";
import { ChatInput } from "../../components/ChatInput/ChatInput";

import { useLoaderData } from "react-router-dom";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { TChatLoader, TMessage } from "../../types/chatTypes";
import { ChatHeader } from "../../components/ChatHeader/ChatHeader";
import toast from "react-hot-toast";

import { useTranslation } from "react-i18next";
import { TVersion } from "../../types";
import { ConversationModal } from "../../components/ConversationModal/ConversationModal";
import { ActionIcon } from "@mantine/core";
import { IconArrowDown } from "@tabler/icons-react";
import {
  linkMessageAttachment,
  triggerAgentTask,
  buildClientDatetimePayload,
  uploadMessageAttachments,
} from "../../modules/apiCalls";
import { agentsInChatSelectionOrder } from "../../modules/agentSelection";

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
    setConversation,
    setSpecifiedUrls,
    setAgentTaskStatus,
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
    setConversation: state.setConversation,
    setSpecifiedUrls: state.setSpecifiedUrls,
    setAgentTaskStatus: state.setAgentTaskStatus,
  }));

  const { t } = useTranslation();

  const activeConversation = conversation ?? loaderData.conversation;
  const isForeignConversation =
    activeConversation?.user_id != null &&
    loaderData.user?.id != null &&
    activeConversation.user_id !== loaderData.user.id;
  const isWidgetConversation = activeConversation?.chat_widget_id != null;
  const isViewer = isForeignConversation || isWidgetConversation;

  const chatMessageContainerRef = useRef<HTMLDivElement>(null);
  const timeoutRef = useRef<number | null>(null);
  const [showScrollToEnd, setShowScrollToEnd] = useState(false);

  useEffect(() => {
    setUser(loaderData.user);
    startup();
  }, [loaderData.user, startup]);

  const [messages, setMessages] = useState<TMessage[]>(
    conversation?.messages || []
  );

  useEffect(() => {
    const handleAgentEvents = (raw: {
      user_id?: number;
      message?: { type: string; conversation_id?: string; version?: TVersion };
    }) => {
      const data = raw?.message;
      if (!data || !conversation?.id || data.conversation_id !== conversation.id)
        return;
      if (data.type === "agent_version_ready" && data.version) {
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

    if (loaderData.conversation) {
      setConversation(loaderData.conversation.id);
    }

    return () => {
      socket.off("agent_events_channel", handleAgentEvents);
    };
  }, [conversation?.id]);

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
    if (
      loaderData.query &&
      agents.length > 0 &&
      messages.length === 0 &&
      loaderData.sendQuery &&
      chatState.selectedAgents.length > 0
    ) {
      handleSendMessage(loaderData.query);
    }
  }, [loaderData.query, agents, chatState.selectedAgents.length]);

  const handleSendMessage = async (input: string) => {
    if (input.trim() === "") return false;

    if (chatState.writtingMode) return false;

    let selectedAgents = agentsInChatSelectionOrder(agents, chatState.selectedAgents);
    if (selectedAgents.length === 0) {
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
    setAgentTaskStatus(t("agent-preparing-request"));

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
      const currentConversation = conversation ?? loaderData.conversation;
      if (!currentConversation?.id) {
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
            currentConversation.id,
            toUpload
          );
          for (const att of uploadRes.attachments) {
            userInputs.push({ type: "input_attachment", attachment_id: att.id });
          }
        }

        for (const rag of ragDocs) {
          const docId = typeof rag.id === "number" ? rag.id : parseInt(String(rag.id), 10);
          if (!isNaN(docId)) {
            const linkRes = await linkMessageAttachment(currentConversation.id, {
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
          const linkRes = await linkMessageAttachment(currentConversation.id, {
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

      const toolNames = ["read_attachment", "list_attachments"];
      if (chatState.webSearch) toolNames.push("explore_web");
      if (chatState.useRag) toolNames.push("rag_query");
      if (chatState.generateImages) toolNames.push("create_image");
      if (chatState.generateSpeech) toolNames.push("create_speech");
      if (chatState.generateVideo) toolNames.push("generate_video");

      await triggerAgentTask({
        conversation_id: currentConversation.id,
        agent_slugs: selectedAgents.map((a) => a.slug),
        user_inputs: userInputs,
        tool_names: toolNames,
        multiagentic_modality: userPreferences.multiagentic_modality,
        client_datetime: buildClientDatetimePayload(),
      });

      cleanAttachments();
      setSpecifiedUrls([]);
      scrollChat();
      return true;
    } catch (error) {
      console.error("Error triggering agent task:", error);
      toast.error(t("agent-task-failed"));
      revertOptimisticSend();
      return false;
    }
  };

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
      const currentConversation = conversation ?? loaderData.conversation;
      if (!currentConversation?.id) return;

      let selectedAgents = agentsInChatSelectionOrder(agents, chatState.selectedAgents);
      if (selectedAgents.length === 0) {
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

      setAgentTaskStatus(t("agent-preparing-request"));

      try {
        const toolNames = ["read_attachment", "list_attachments"];
        if (chatState.webSearch) toolNames.push("explore_web");
        if (chatState.useRag) toolNames.push("rag_query");
        if (chatState.generateImages) toolNames.push("create_image");
        if (chatState.generateSpeech) toolNames.push("create_speech");
        if (chatState.generateVideo) toolNames.push("generate_video");

        await triggerAgentTask({
          conversation_id: currentConversation.id,
          agent_slugs: selectedAgents.map((a) => a.slug),
          user_inputs: [{ type: "input_text", text: newText }],
          tool_names: toolNames,
          multiagentic_modality: userPreferences.multiagentic_modality,
          regenerate_message_id: regenPayload.userId,
          client_datetime: buildClientDatetimePayload(),
        });

        scrollChat();
      } catch (error) {
        console.error("Error regenerating via agent task:", error);
        toast.error(t("agent-task-failed"));
        setAgentTaskStatus(null);
        setMessages((prev) => {
          const last = prev[prev.length - 1];
          if (last?.type === "assistant" && !last.id) return prev.slice(0, -1);
          return prev;
        });
        void setConversation(currentConversation.id);
      }
    },
    [
      agents,
      chatState,
      conversation,
      isViewer,
      loaderData.conversation,
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
          right={
            <ConversationModal
              conversation={conversation || loaderData.conversation}
              readOnly={isViewer}
            />
          }
        />

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
            readOnly={isViewer}
          />
        </div>
      </div>
    </main>
  );
}
