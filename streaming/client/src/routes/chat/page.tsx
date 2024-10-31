import React, { useEffect, useState } from "react";
import axios from "axios";
import io from "socket.io-client";
import "./page.css";
import { Message } from "../../components/Message/Message";
import { ChatInput } from "../../components/ChatInput/ChatInput";

import { useLoaderData } from "react-router-dom";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import { useStore } from "../../modules/store";
import { TChatLoader, TMessage } from "../../types/chatTypes";
import { ChatHeader } from "../../components/ChatHeader/ChatHeader";
import toast, { Toaster } from "react-hot-toast";
import { playAudioFromBytes } from "../../modules/utils";
import { TrainingModals } from "../../components/TrainingModals/TrainingModals";

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
  }));

  useEffect(() => {
    setUser(loaderData.user);
  }, []);

  const [messages, setMessages] = useState(
    loaderData.conversation.messages as TMessage[]
  );

  useEffect(() => {
    const updateMessages = (chunk: string, agentSlug: string) => {
      const newMessages = [...messages];
      const lastMessage = newMessages[newMessages.length - 1];

      if (
        lastMessage &&
        lastMessage.type === "assistant" &&
        lastMessage.agentSlug === agentSlug
      ) {
        lastMessage.text += chunk;
      } else {
        const assistantMessage = {
          type: "assistant",
          text: chunk,
          attachments: [],
          agentSlug: agentSlug,
        };
        newMessages.push(assistantMessage);
      }
      return newMessages;
    };

    socket.on("response", (data) => {
      setMessages(updateMessages(data.chunk, data.agent_slug));
    });
    socket.on("audio-file", (audioFile) => {
      playAudioFromBytes(audioFile);
    });

    socket.on("responseFinished", (data) => {
      console.log("Response finished:", data);
    });
    socket.on("sources", (data) => {
      console.log("Sources:", data);
    });
    socket.on("notification", (data) => {
      console.log("Receiving notification:", data);
      toast.success(data.message);
      // socket.disconnect();
    });

    return () => {
      socket.off("response");
      socket.off("audio-file");
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
    setMessages([...messages, userMessage]);

    try {
      const token = localStorage.getItem("token");

      socket.emit("message", {
        message: userMessage,
        context: messages.map((msg) => `${msg.type}: ${msg.text}`).join("\n"),
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

  const handleGenerateSpeech = async (text) => {
    try {
      socket.emit("speech_request", {
        text,
      });
    } catch (error) {
      console.error("Error generating speech:", error);
    }
  };

  const handleGenerateImage = async (text) => {
    try {
      const response = await axios.post(
        "/generate_image/",
        { prompt: text },
        {
          headers: {
            Authorization: `Token ${token}`,
          },
        }
      );
      const imageUrl = response.data.image_url;

      const imageMessage = {
        type: "assistant",
        text: "",
        attachments: [
          {
            type: "image",
            content: imageUrl,
            name: "Generated image",
            file: null,
          },
        ],
      };
      setMessages([...messages, imageMessage]);
    } catch (error) {
      console.error("Error generating image:", error);

      toast.error(
        "Error generating image: " + error.response?.data?.detail?.message ||
          error.message
      );
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

  return (
    <>
      <TrainingModals />
      {chatState.isSidebarOpened && <Sidebar />}
      <div className="chat-container">
        <ChatHeader />
        <ChatInput
          handleSendMessage={handleSendMessage}
          handleKeyDown={handleKeyDown}
          conversation={conversation || loaderData.conversation}
        />

        <div className="chat-messages">
          {conversation && conversation.title ? (
            <h3 className="padding-medium text-center">{conversation.title}</h3>
          ) : loaderData.conversation.title ? (
            <h3 className="padding-medium text-center">
              {loaderData.conversation.title}
            </h3>
          ) : (
            ""
          )}

          {messages &&
            messages.map((msg, index) => (
              <Message
                {...msg}
                key={index}
                index={index}
                onGenerateSpeech={handleGenerateSpeech}
                onGenerateImage={handleGenerateImage}
              />
            ))}
        </div>
      </div>
    </>
  );
}
