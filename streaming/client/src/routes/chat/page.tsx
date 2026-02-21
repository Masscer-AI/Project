import React, { useEffect, useState } from "react";
// import axios from "axios";
import { Message } from "../../components/Message/Message";
import { ChatInput } from "../../components/ChatInput/ChatInput";

import { useLoaderData, useSearchParams } from "react-router-dom";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { TChatLoader, TMessage } from "../../types/chatTypes";
import { ChatHeader } from "../../components/ChatHeader/ChatHeader";
import toast from "react-hot-toast";

import { useTranslation } from "react-i18next";
import { TVersion } from "../../types";
import { updateLastMessagesIds } from "./helpers";
import { ConversationModal } from "../../components/ConversationModal/ConversationModal";
import { ActionIcon } from "@mantine/core";
import { IconArrowDown } from "@tabler/icons-react";
import { useIsFeatureEnabled } from "../../hooks/useFeatureFlag";
import {
  linkMessageAttachment,
  triggerAgentTask,
  uploadMessageAttachments,
} from "../../modules/apiCalls";

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
  }));

  const { t } = useTranslation();
  const isAgentTaskEnabled = useIsFeatureEnabled("agent-task");
  const useAgentTaskPath =
    isAgentTaskEnabled && (chatState.useAgentTask ?? true);

  const activeConversation = conversation ?? loaderData.conversation;
  const isViewer =
    activeConversation?.user_id != null &&
    loaderData.user?.id != null &&
    activeConversation.user_id !== loaderData.user.id;

  const chatMessageContainerRef = React.useRef<HTMLDivElement>(null);
  // const [searchParams, setSearchParams] = useSearchParams();

  const timeoutRef = React.useRef<number | null>(null);
  const [showScrollToEnd, setShowScrollToEnd] = useState(false);

  useEffect(() => {
    setUser(loaderData.user);
    startup();
  }, [loaderData.user, startup]);

  const [messages, setMessages] = useState<TMessage[]>(
    // loaderData.conversation.messages || conversation?.messages || []
    conversation?.messages || []
  );

  useEffect(() => {
    socket.on("responseFinished", (data) => {
      console.log("Response finished:", data);
      setMessages((prevMessages) =>
        updateLastMessagesIds(data, prevMessages, data.next_agent_slug)
      );
    });

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
      socket.off("responseFinished");
      socket.off("agent_events_channel", handleAgentEvents);
    };
  }, [conversation?.id]);

  const scrollChat = () => {
    const container = chatMessageContainerRef.current;
    if (!container) return;
    const start = container.scrollTop;
    const end = container.scrollHeight;
    const duration = 1000; // Duración en milisegundos
    const startTime = performance.now();

    const smoothScroll = (currentTime) => {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1); // Normalizar entre 0 y 1
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

  const updateScrollToEndVisibility = React.useCallback(() => {
    const container = chatMessageContainerRef.current;
    if (!container) return;
    const remaining =
      container.scrollHeight - container.scrollTop - container.clientHeight;
    setShowScrollToEnd(remaining > 60);
  }, []);

  const handleAutoScroll = () => {
    if (chatMessageContainerRef.current && userPreferences.autoscroll) {
      if (timeoutRef.current) {
        return;
      }

      timeoutRef.current = setTimeout(() => {
        scrollChat();
      }, 1000);
    }
  };

  useEffect(() => {
    socket.on("response", (data) => {
      handleAutoScroll();
    });

    return () => {
      socket.off("response");
    };
  }, [chatMessageContainerRef, userPreferences.autoscroll]);

  useEffect(() => {
    // toast.success("Loading conversation...");
    if (!conversation?.messages) {
      // toast.error("Conversation not found");
      return;
    }
    // toast.success("Conversation loaded");
    setMessages(conversation?.messages);
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

  // useEffect(() => {
  //   if (loaderData.conversation) {
  //     loaderData.conversation.messages;
  //   }
  // }, [loaderData.conversation]);

  useEffect(() => {
    if (
      loaderData.query &&
      agents.length > 0 &&
      messages.length === 0 &&
      loaderData.sendQuery
    ) {
      handleSendMessage(loaderData.query);
    }
  }, [loaderData.query, agents]);

  const handleSendMessage = async (input: string) => {
    if (input.trim() === "") return false;

    if (chatState.writtingMode) return false;

    const userMessage: TMessage = {
      type: "user",
      text: input,
      attachments: chatState.attachments,
      index: messages.length,
    };

    let selectedAgents = agents.filter((a) => a.selected);
    if (selectedAgents.length === 0) {
      toast.error(t("select-at-least-one-agent-to-chat"));
      return false;
    }

    selectedAgents = selectedAgents.sort(
      (a, b) =>
        chatState.selectedAgents.indexOf(a.slug) -
        chatState.selectedAgents.indexOf(b.slug)
    );

    const assistantMessage: TMessage = {
      type: "assistant",
      text: "",
      attachments: [],
      agent_slug: selectedAgents[0].slug,
    };
    setMessages([...messages, userMessage, assistantMessage]);

    // --- Agent Task route (feature flag gated + user preference) ---
    if (useAgentTaskPath) {
      try {
        const currentConversation = conversation ?? loaderData.conversation;
        if (!currentConversation?.id) {
          toast.error("No conversation found");
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

        // Website attachments (specified URLs)
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

          // Update UI user message to show website attachments immediately
          if (uiWebsiteAttachments.length > 0) {
            setMessages((prev) => {
              const updated = [...prev];
              const userIdx = updated.length - 2; // user message is before assistant placeholder
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
        if (chatState.webSearch) {
          toolNames.push("explore_web");
        }
        if (chatState.useRag) {
          toolNames.push("rag_query");
        }
        if (chatState.generateImages) {
          toolNames.push("create_image");
        }
        if (chatState.generateSpeech) {
          toolNames.push("create_speech");
        }

        await triggerAgentTask({
          conversation_id: currentConversation.id,
          agent_slugs: selectedAgents.map((a) => a.slug),
          user_inputs: userInputs,
          tool_names: toolNames,
          plugin_slugs: (chatState.selectedPlugins || []).map((p) => p.slug),
          multiagentic_modality: userPreferences.multiagentic_modality,
        });

        cleanAttachments();
        setSpecifiedUrls([]);
        scrollChat();
        return true;
      } catch (error) {
        console.error("Error triggering agent task:", error);
        toast.error(t("agent-task-failed"));
        return false;
      }
    }

    // --- Normal streaming route ---
    const memoryMessages = [...messages]
      .reverse()
      .slice(0, userPreferences.max_memory_messages)
      .reverse()
      .map((m) => {
        const { attachments, ...rest } = m;
        return rest;
      });

    try {
      const token = localStorage.getItem("token");

      // @ts-ignore
      userMessage.agents = selectedAgents.map((a) => ({
        slug: a.slug,
        name: a.name,
      }));

      socket.emit("message", {
        message: userMessage,
        context: memoryMessages,
        plugins: chatState.selectedPlugins,
        token: token,
        models_to_complete: selectedAgents,
        conversation: conversation ? conversation : loaderData.conversation,
        web_search_activated: chatState.webSearch,
        specified_urls: chatState.specifiedUrls || [],
        use_rag: chatState.useRag,
        multiagentic_modality: userPreferences.multiagentic_modality,
      });

      cleanAttachments();
      scrollChat();
      return true;
    } catch (error) {
      console.error("Error sending message:", error);
      return false;
    }
  };

  const handleRegenerateConversation = (
    userMessage: TMessage,
    prevMessages: TMessage[]
  ) => {
    try {
      // const selectedAgents = agents.filter((a) => a.selected);
      let selectedAgents = agents.filter((a) => a.selected);
      if (selectedAgents.length === 0) {
        toast.error(t("select-at-least-one-agent-to-chat"));
        return false;
      }

      selectedAgents = selectedAgents.sort(
        (a, b) =>
          chatState.selectedAgents.indexOf(a.slug) -
          chatState.selectedAgents.indexOf(b.slug)
      );

      const token = localStorage.getItem("token");

      userMessage.attachments = chatState.attachments;
      userMessage.agents = selectedAgents.map((a) => ({
        slug: a.slug,
        name: a.name,
      }));

      const assistantMessage: TMessage = {
        type: "assistant",
        text: "",
        attachments: [],
        agent_slug: selectedAgents[0].slug,
      };

      setMessages([...prevMessages, assistantMessage]);

      socket.emit("message", {
        message: userMessage,
        context: prevMessages,
        plugins: chatState.selectedPlugins,
        token: token,
        models_to_complete: selectedAgents,
        conversation: conversation ? conversation : loaderData.conversation,
        web_search_activated: chatState.webSearch,
        use_rag: chatState.useRag,
        regenerate: {
          user_message_id: userMessage.id,
        },
      });

      cleanAttachments();
    } catch (error) {
      console.error("Error sending message:", error);
    }
  };

  const onImageGenerated = (
    imageContentB64: string,
    imageName: string,
    message_id: number
  ) => {
    setMessages((prevMessages) => {
      const messageIndex = prevMessages.findIndex((m) => m.id === message_id);
      if (messageIndex === -1) return prevMessages;

      const copyMessages = [...prevMessages];
      copyMessages[messageIndex].attachments = [
        ...(copyMessages[messageIndex].attachments || []),
        {
          type: "image",
          content: imageContentB64,
          name: imageName,
          file: null,
          text: "",
        },
      ];
      return copyMessages;
    });
  };

  const onMessageEdit = (
    index: number,
    text: string,
    versions?: TVersion[]
  ) => {
    const message = messages[index];
    if (!message) return;

    if (message.type === "user") {
      if (useAgentTaskPath && message.id) {
        handleRegenerateAgentTask(message, index, text);
      } else {
        const newMessages = messages.slice(0, index + 1);
        newMessages[index].text = text;
        message.index = index;
        handleRegenerateConversation(message, newMessages);
      }
    }
    if (message.type === "assistant" && versions) {
      const messagesCopy = [...messages];
      messagesCopy[index].versions = versions;
      setMessages(messagesCopy);
    }
  };

  const handleRegenerateAgentTask = async (
    userMessage: TMessage,
    index: number,
    newText: string
  ) => {
    const currentConversation = conversation ?? loaderData.conversation;
    if (!currentConversation?.id || !userMessage.id) return;

    let selectedAgents = agents.filter((a) => a.selected);
    if (selectedAgents.length === 0) {
      toast.error(t("select-at-least-one-agent-to-chat"));
      return;
    }
    selectedAgents = selectedAgents.sort(
      (a, b) =>
        chatState.selectedAgents.indexOf(a.slug) -
        chatState.selectedAgents.indexOf(b.slug)
    );

    const truncated = messages.slice(0, index + 1);
    truncated[index] = { ...truncated[index], text: newText };

    const assistantMessage: TMessage = {
      type: "assistant",
      text: "",
      attachments: [],
      agent_slug: selectedAgents[0].slug,
    };
    setMessages([...truncated, assistantMessage]);

    try {
      const toolNames = ["read_attachment", "list_attachments"];
      if (chatState.webSearch) toolNames.push("explore_web");
      if (chatState.useRag) toolNames.push("rag_query");
      if (chatState.generateImages) toolNames.push("create_image");
      if (chatState.generateSpeech) toolNames.push("create_speech");

      await triggerAgentTask({
        conversation_id: currentConversation.id,
        agent_slugs: selectedAgents.map((a) => a.slug),
        user_inputs: [{ type: "input_text", text: newText }],
        tool_names: toolNames,
        plugin_slugs: (chatState.selectedPlugins || []).map((p) => p.slug),
        multiagentic_modality: userPreferences.multiagentic_modality,
        regenerate_message_id: userMessage.id,
      });

      scrollChat();
    } catch (error) {
      console.error("Error regenerating via agent task:", error);
      toast.error(t("agent-task-failed"));
    }
  };

  const onMessageDeleted = (index: number) => {
    const newMessages = messages.filter((_, i) => i !== index);
    setMessages(newMessages);
  };

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
      <div className="flex flex-col h-screen w-full md:mx-auto md:max-w-[900px] relative z-10 px-0 md:px-4 py-0 md:py-6 overflow-visible">
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
          className="flex-1 overflow-y-auto flex flex-col w-full pb-6 mt-6 px-1 md:px-2"
        >
          {messages &&
            messages.map((msg, index) => (
              <Message
                {...msg}
                key={index + msg.text + JSON.stringify(msg.versions)}
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
        <ChatInput
          handleSendMessage={handleSendMessage}
          initialInput={
            loaderData.query && !loaderData.sendQuery ? loaderData.query : ""
          }
          readOnly={isViewer}
        />
      </div>
    </main>
  );
}
