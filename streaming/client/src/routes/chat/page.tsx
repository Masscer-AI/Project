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

const socket = io("http://localhost:8001", { autoConnect: false });

export default function ChatView() {
  const loaderData = useLoaderData() as TChatLoader;

  const { chatState, input, setInput, model, conversation } = useStore(
    (state) => ({
      chatState: state.chatState,
      toggleSidebar: state.toggleSidebar,
      input: state.input,
      setInput: state.setInput,
      model: state.model,
      conversation: state.conversation,
    })
  );

  const [messages, setMessages] = useState(
    loaderData.conversation.messages as TMessage[]
  );

  useEffect(() => {
    socket.on("connect", () => {
      console.log("Connected to socket server");
    });

    socket.on("disconnect", () => {
      console.log("Disconnected from socket server");
    });

    const updateMessages = (chunk: string) => {
      const newMessages = [...messages];
      const lastMessage = newMessages[newMessages.length - 1];

      if (lastMessage && lastMessage.type === "assistant") {
        lastMessage.text += chunk;
      } else {
        const assistantMessage = {
          type: "assistant",
          text: chunk,
        };
        newMessages.push(assistantMessage);
      }
      return newMessages;
    };

    socket.on("response", (data) => {
      setMessages(updateMessages(data.chunk));
    });

    socket.on("responseFinished", (data) => {
      console.log("Response finished:", data);
      socket.disconnect();
    });

    return () => {
      socket.off("connect");
      socket.off("disconnect");
      socket.off("response");
      socket.off("responseFinished");
    };
  }, [messages]);

  useEffect(() => {
    if (!conversation?.messages) return;
    setMessages(conversation?.messages);
  }, [conversation]);

  const handleSendMessage = async () => {
    if (input.trim() === "") return;

    socket.connect();

    console.log(messages, "MESSAGES");

    const userMessage = { type: "user", text: input };
    setMessages([...messages, userMessage]);

    try {
      const token = localStorage.getItem("token");
      // TODO: MEssage should be an object
      socket.emit("message", {
        message: input,
        context: messages.map((msg) => `${msg.type}: ${msg.text}`).join("\n"),
        model: model,
        token: token,
        conversation: conversation ? conversation : loaderData.conversation,
      });

      setInput("");
    } catch (error) {
      console.error("Error sending message:", error);
    }
  };

  const handleGenerateSpeech = async (text) => {
    try {
      const token = localStorage.getItem("token");
      const response = await axios.post(
        "/generate_speech/",
        { text },
        {
          headers: {
            Authorization: `Token ${token}`,
          },
          responseType: "blob",
        }
      );
      const audioBlob = new Blob([response.data], { type: "audio/mpeg" });
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      audio.play();
    } catch (error) {
      console.error("Error generating speech:", error);
    }
  };

  const handleGenerateImage = async (text) => {
    try {
      const token = localStorage.getItem("token");
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
        imageUrl,
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
    if (event.key === "Enter") {
      handleSendMessage();
    } else {
      setInput(event.target.value);
    }
  };

  return (
    <>
      <Toaster />
      {chatState.isSidebarOpened && <Sidebar />}
      <div className="chat-container">
        <ChatHeader />
        <ChatInput
          handleSendMessage={handleSendMessage}
          handleKeyDown={handleKeyDown}
        />
        <div className="chat-messages">
          {messages &&
            messages.map((msg, index) => (
              <Message
                key={index}
                sender={msg.type}
                text={msg.text}
                imageUrl={msg.imageUrl}
                onGenerateSpeech={handleGenerateSpeech}
                onGenerateImage={handleGenerateImage}
              />
            ))}
        </div>
      </div>
    </>
  );
}
