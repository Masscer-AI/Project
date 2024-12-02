import React, { useEffect, useState } from "react";
import axios from "axios";
import "./page.css";
import { Message } from "../../components/Message/Message";
import { ChatInput } from "../../components/ChatInput/ChatInput";

import { useLoaderData } from "react-router-dom";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { TChatLoader, TMessage } from "../../types/chatTypes";
import { ChatHeader } from "../../components/ChatHeader/ChatHeader";
import toast from "react-hot-toast";

import { updateConversation } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { TVersion } from "../../types";
import { updateLastMessagesIds, addAssistantMessageChunk } from "./helpers";

export default function ChatView() {
  const loaderData = useLoaderData() as TChatLoader;

  const {
    chatState,
    input,
    setInput,
    conversation,
    cleanAttachments,
    socket,
    setUser,
    agents,
    startup,
    userPreferences,
  } = useStore((state) => ({
    socket: state.socket,
    chatState: state.chatState,
    toggleSidebar: state.toggleSidebar,
    input: state.input,
    setInput: state.setInput,
    conversation: state.conversation,
    cleanAttachments: state.cleanAttachments,
    modelsAndAgents: state.modelsAndAgents,
    setUser: state.setUser,
    agents: state.agents,
    startup: state.startup,
    userPreferences: state.userPreferences,
  }));

  const { t } = useTranslation();
  const chatMessageContainerRef = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    setUser(loaderData.user);
    startup();
    setInput(loaderData.query || "");
  }, []);
  const [messages, setMessages] = useState<TMessage[]>(
    loaderData.conversation.messages
  );

  useEffect(() => {
    socket.on("response", (data) => {
      setMessages((prevMessages) =>
        addAssistantMessageChunk(
          data.chunk,
          data.agent_slug,
          prevMessages,
          userPreferences.multiagentic_modality
        )
      );
      if (chatMessageContainerRef.current && userPreferences.autoscroll) {
        chatMessageContainerRef.current.scrollTop =
          chatMessageContainerRef.current.scrollHeight;
      }
    });

    socket.on("responseFinished", (data) => {
      console.log("Response finished:", data);
      setMessages((prevMessages) => updateLastMessagesIds(data, prevMessages));
    });
    socket.on("sources", (data) => {
      console.log("Sources:", data);
    });
    socket.on("notification", (data) => {
      console.log("Receiving notification:", data);
      toast.success(data.message);
    });

    return () => {
      socket.off("response");
      socket.off("responseFinished");
      socket.off("notification");
      socket.off("sources");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length]);

  useEffect(() => {
    if (!conversation?.messages) return;
    setMessages(conversation?.messages);
  }, [conversation]);

  useEffect(() => {
    if (
      loaderData.query &&
      input === loaderData.query &&
      agents.length > 0 &&
      messages.length === 0
    ) {
      handleSendMessage();
    }
  }, [loaderData.query, input, agents]);

  const handleSendMessage = async () => {
    if (input.trim() === "") return;

    if (chatState.writtingMode) return;

    let selectedAgents = agents.filter((a) => a.selected);

    const userMessage = {
      type: "user",
      text: input,
      attachments: chatState.attachments,
    };

    if (selectedAgents.length === 0) {
      toast.error(t("select-at-least-one-agent-to-chat"));
      return;
    }
    // reorder the agents based on its slug and position in the chatState.selectedAgents
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
      .reverse();

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
        token: token,
        models_to_complete: selectedAgents,
        conversation: conversation ? conversation : loaderData.conversation,
        web_search_activated: chatState.webSearch,
        use_rag: chatState.useRag,
        multiagentic_modality: userPreferences.multiagentic_modality,
      });

      setInput("");
      // cleanAttachments();
    } catch (error) {
      console.error("Error sending message:", error);
    }
  };

  const handleRegenerateConversation = (
    userMessage: TMessage,
    context: TMessage[]
  ) => {
    try {
      const selectedAgents = agents.filter((a) => a.selected);
      const token = localStorage.getItem("token");

      userMessage.attachments = chatState.attachments;
      userMessage.agents = selectedAgents.map((a) => ({
        slug: a.slug,
        name: a.name,
      }));

      socket.emit("message", {
        message: userMessage,
        context: context,
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

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && event.shiftKey) {
      setInput(event.target.value);
      return;
    } else if (event.key === "Enter") {
      handleSendMessage();
    } else {
      setInput(event.target.value);
    }
  };

  const onTitleEdit = async (title: string) => {
    if (!conversation?.id && !loaderData.conversation.id) return;

    await updateConversation(conversation?.id || loaderData.conversation.id, {
      title,
    });

    toast.success(t("title-updated"));
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
      setMessages(newMessages);
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
      {chatState.isSidebarOpened && <Sidebar />}
      <div className="chat-container">
        {userPreferences.background_image_source && (
          <img
            style={{ opacity: userPreferences.background_image_opacity }}
            className="pos-absolute"
            src={userPreferences.background_image_source}
          />
        )}
        <ChatHeader
          onTitleEdit={onTitleEdit}
          title={conversation?.title || loaderData.conversation.title || "Chat"}
        />

        <div ref={chatMessageContainerRef} className="chat-messages">
          {messages &&
            messages.map((msg, index) => (
              <Message
                {...msg}
                key={index}
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
          handleKeyDown={handleKeyDown}
          conversation={conversation || loaderData.conversation}
        />
      </div>
    </main>
  );
}
