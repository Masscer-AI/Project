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
import { createAudioPlayer, playAudioFromBytes } from "../../modules/utils";

import { generateImage, updateConversation } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { TVersion } from "../../types";
import { updateLastMessagesIds, updateMessages } from "./helpers";
import { SvgButton } from "../../components/SvgButton/SvgButton";

export default function ChatView() {
  const loaderData = useLoaderData() as TChatLoader;

  const token = localStorage.getItem("token");
  const {
    chatState,
    input,
    setInput,
    model,
    conversation,
    cleanAttachments,
    socket,
    setUser,
    agents,
    startup,
  } = useStore((state) => ({
    socket: state.socket,
    chatState: state.chatState,
    toggleSidebar: state.toggleSidebar,
    input: state.input,
    setInput: state.setInput,
    model: state.model,
    conversation: state.conversation,
    cleanAttachments: state.cleanAttachments,
    modelsAndAgents: state.modelsAndAgents,
    setUser: state.setUser,
    agents: state.agents,
    startup: state.startup,
  }));

  const { t } = useTranslation();

  useEffect(() => {
    setUser(loaderData.user);
    startup();
  }, []);

  const [messages, setMessages] = useState(
    loaderData.conversation.messages as TMessage[]
  );

  useEffect(() => {
    socket.on("response", (data) => {
      setMessages((prevMessages) =>
        updateMessages(data.chunk, data.agent_slug, prevMessages)
      );
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
      // socket.off("audio-file");
      socket.off("responseFinished");
      socket.off("notification");
      socket.off("sources");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  useEffect(() => {
    if (!conversation?.messages) return;
    setMessages(conversation?.messages);
  }, [conversation]);

  const handleSendMessage = async () => {
    if (input.trim() === "") return;

    if (chatState.writtingMode) return;

    const selectedAgents = agents.filter((a) => a.selected);

    if (selectedAgents.length === 0) {
      toast.error("You must select at least one agent to complete! 👀");
      return;
    }

    const userMessage = {
      type: "user",
      text: input,
      attachments: chatState.attachments,
    };
    const assistantMessage: TMessage = {
      type: "assistant",
      text: "",
      attachments: [],
    };
    setMessages([...messages, userMessage, assistantMessage]);

    try {
      const token = localStorage.getItem("token");

      socket.emit("message", {
        message: userMessage,
        context: messages,
        model: model,
        token: token,
        models_to_complete: selectedAgents,
        conversation: conversation ? conversation : loaderData.conversation,
        web_search_activated: chatState.webSearch,
        use_rag: chatState.useRag,
      });

      setInput("");
      cleanAttachments();
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

      socket.emit("message", {
        message: userMessage,
        context: context,
        model: model,
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

  const handleGenerateImage = async (text, message_id) => {
    try {
      const messageIndex = messages.findIndex((m) => m.id === message_id);
      if (messageIndex === -1) return;
      toast.loading(t("generating-image"));

      const response = await generateImage(text, message_id);

      toast.dismiss();
      const imageUrl = response.image_url;

      setMessages((prevMessages) => {
        const copyMessages = [...prevMessages];
        copyMessages[messageIndex].attachments = [
          ...(copyMessages[messageIndex].attachments || []),
          {
            type: "image",
            content: imageUrl,
            name: "Generated image",
            file: null,
          },
        ];
        return copyMessages;
      });
      toast.success(t("image-generated"));
    } catch (error) {
      toast.dismiss();
      console.error("Error generating image:", error);

      toast.error(t("error-generating-image") + error.response.data.error);
    }
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

  return (
    <>
      <div className="d-flex">
        {chatState.isSidebarOpened && <Sidebar />}
        <div className="chat-container">
          <ChatHeader
            onTitleEdit={onTitleEdit}
            title={
              conversation?.title || loaderData.conversation.title || "Chat"
            }
          />
          <ChatInput
            handleSendMessage={handleSendMessage}
            handleKeyDown={handleKeyDown}
            conversation={conversation || loaderData.conversation}
          />

          <div className="chat-messages">
            {messages &&
              messages.map((msg, index) => (
                <Message
                  {...msg}
                  key={index}
                  index={index}
                  // onGenerateSpeech={handleGenerateSpeech}
                  onGenerateImage={handleGenerateImage}
                  onMessageEdit={onMessageEdit}
                />
              ))}
          </div>
        </div>
      </div>
    </>
  );
}
