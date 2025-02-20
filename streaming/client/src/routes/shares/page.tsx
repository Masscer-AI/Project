import React, { useEffect, useState } from "react";

import { Message } from "../../components/Message/Message";

import { useLoaderData } from "react-router-dom";

import { useStore } from "../../modules/store";
import { TChatLoader, TMessage } from "../../types/chatTypes";

import { useTranslation } from "react-i18next";
import { TVersion } from "../../types";

export default function SharedChatView() {
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
  }));

  const { t } = useTranslation();

  useEffect(() => {
    setUser(loaderData.user);
    startup();
  }, []);

  const [messages, setMessages] = useState(
    // @ts-ignore
    loaderData.conversation.messages as TMessage[]
  );

  useEffect(() => {
    if (!conversation?.messages) return;
    setMessages(conversation?.messages);
  }, [conversation]);

  const handleRegenerateConversation = (
    userMessage: TMessage,
    context: TMessage[]
  ) => {
    try {
      const selectedAgents = agents.filter((a) => a.selected);
      const token = localStorage.getItem("token");

      userMessage.attachments = chatState.attachments;

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

  const onImageGenerated = (imageUrl: string, message_id: number) => {
    setMessages((prevMessages) => {
      const messageIndex = prevMessages.findIndex((m) => m.id === message_id);
      if (messageIndex === -1) return prevMessages;

      const copyMessages = [...prevMessages];
      copyMessages[messageIndex].attachments = [
        ...(copyMessages[messageIndex].attachments || []),
        {
          type: "image",
          content: imageUrl,
          name: "Generated image",
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
      setMessages(newMessages);
      handleRegenerateConversation(message, newMessages);
    }
    if (message.type === "assistant" && versions) {
      const messagesCopy = [...messages];
      messagesCopy[index].versions = versions;
      setMessages(messagesCopy);
    }
  };

  return (
    <>
      <div className="d-flex">
        {/* {chatState.isSidebarOpened && <Sidebar />} */}
        <div className="chat-container">
          <div className="chat-messages">
            <h2 className="padding-medium my-medium">
              {loaderData.conversation.title}
            </h2>
            {messages &&
              messages.map((msg, index) => (
                <Message
                  {...msg}
                  key={index}
                  index={index}
                  // @ts-ignore
                  onImageGenerated={() => {}}
                  onMessageEdit={onMessageEdit}
                  onMessageDeleted={() => {}}
                  numberMessages={messages.length}
                />
              ))}
          </div>
        </div>
      </div>
    </>
  );
}
