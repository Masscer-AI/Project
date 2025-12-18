import React, { useEffect, useState } from "react";
// import axios from "axios";
import "./page.css";
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
import { updateLastMessagesIds } from "./helpers";
import { ConversationModal } from "../../components/ConversationModal/ConversationModal";

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
  }));

  const { t } = useTranslation();
  const chatMessageContainerRef = React.useRef<HTMLDivElement>(null);
  // const [searchParams, setSearchParams] = useSearchParams();

  const timeoutRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    setUser(loaderData.user);
    startup();
  }, [loaderData.user, startup]);

  const [messages, setMessages] = useState<TMessage[]>(
    // loaderData.conversation.messages || conversation?.messages || []
    conversation?.messages || []
  );

  useEffect(() => {
    socket.on("responseFinished", (data: any) => {
      console.log("Response finished:", data);
      setMessages((prevMessages) =>
        updateLastMessagesIds(data, prevMessages, data.next_agent_slug)
      );
    });

    if (loaderData.conversation) {
      // setMessages(loaderData.conversation.messages || []);
      setConversation(loaderData.conversation.id);
    }

    return () => {
      socket.off("responseFinished");
    };
  }, []);

  const scrollChat = () => {
    const container = chatMessageContainerRef.current;
    if (!container) return;
    const start = container.scrollTop;
    const end = container.scrollHeight;
    const duration = 1000; // Duración en milisegundos
    const startTime = performance.now();

    const smoothScroll = (currentTime: number) => {
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
    socket.on("response", (_data: any) => {
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

      // cleanAttachments();
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
      const newMessages = messages.slice(0, index + 1);
      newMessages[index].text = text;
      message.index = index;
      handleRegenerateConversation(message, newMessages);
    }
    if (message.type === "assistant" && versions) {
      const messagesCopy = [...messages];
      messagesCopy[index].versions = versions;
      setMessages(messagesCopy);
    }
  };

  const onMessageDeleted = (index: number) => {
    const newMessages = messages.filter((_, i) => i !== index);
    setMessages(newMessages);
  };

  return (
    <main className="d-flex chat-page">
      {userPreferences.background_image_source && (
        <img
          style={{ opacity: userPreferences.background_image_opacity }}
          className="pos-absolute"
          src={userPreferences.background_image_source}
        />
      )}
      {chatState.isSidebarOpened && <Sidebar />}
      <div className="chat-container">
        <ChatHeader
          right={
            <ConversationModal
              conversation={conversation || loaderData.conversation}
            />
          }
        />

        <div ref={chatMessageContainerRef} className="chat-messages">
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
              />
            ))}
        </div>
        <ChatInput
          handleSendMessage={handleSendMessage}
          initialInput={
            loaderData.query && !loaderData.sendQuery ? loaderData.query : ""
          }
        />
      </div>
    </main>
  );
}
