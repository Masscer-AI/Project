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

const socket = io("http://localhost:8001", {
  autoConnect: false,
  transports: ["websockets", "polling"],
});

export default function ChatView() {
  const loaderData = useLoaderData() as TChatLoader;

  const token = localStorage.getItem("token");
  const { chatState, input, setInput, model, conversation, cleanAttachments } =
    useStore((state) => ({
      chatState: state.chatState,
      toggleSidebar: state.toggleSidebar,
      input: state.input,
      setInput: state.setInput,
      model: state.model,
      conversation: state.conversation,
      cleanAttachments: state.cleanAttachments,
    }));

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
          attachments: [],
        };
        newMessages.push(assistantMessage);
      }
      return newMessages;
    };

    socket.on("response", (data) => {
      setMessages(updateMessages(data.chunk));
    });
    socket.on("audio-file", (audioFile) => {
      playAudioFromBytes(audioFile);
    });

    socket.on("responseFinished", (data) => {
      console.log("Response finished:", data);
      socket.disconnect();
    });

    return () => {
      socket.off("connect");
      socket.off("disconnect");
      socket.off("response");
      socket.off("audio-file");
      socket.off("responseFinished");
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages]);

  useEffect(() => {
    if (!conversation?.messages) return;
    setMessages(conversation?.messages);
  }, [conversation]);

  const handleSendMessage = async () => {
    if (input.trim() === "") return;

    socket.connect();
    const userMessage = {
      type: "user",
      text: input,
      attachments: chatState.attachments,
    };
    setMessages([...messages, userMessage]);

    try {
      const token = localStorage.getItem("token");
      socket.emit(
        "message",
        {
          message: {
            type: "user",
            text: input,
            attachments: chatState.attachments,
          },
          context: messages.map((msg) => `${msg.type}: ${msg.text}`).join("\n"),
          model: model,
          token: token,
          conversation: conversation ? conversation : loaderData.conversation,
        },
        (ack) => {
          console.log(ack, "ACK FROM SERVER ?");
        }
      );

      setInput("");
      cleanAttachments();
    } catch (error) {
      console.error("Error sending message:", error);
    }
  };

  const handleGenerateSpeech = async (text) => {
    try {
      socket.connect();

      // TODO: Send the token in every socket event, maybe we need to have a socket manager for the client ir order to have a straightforward interface
      // const token = localStorage.getItem("token");
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

  const handleKeyDown = (event, isWritingMode) => {
    if (isWritingMode) {
      if (event.key === "Enter") {
        return
      }
    } else {
      if (event.key === "Enter" && event.shiftKey) {
        setInput(event.target.value)
        return;
      } else if (event.key === "Enter") {
        handleSendMessage();
      } else {
        setInput(event.target.value);
      }
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
                {...msg}
                key={index}
                onGenerateSpeech={handleGenerateSpeech}
                onGenerateImage={handleGenerateImage}
              />
            ))}
        </div>
      </div>
    </>
  );
}
