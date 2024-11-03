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
import { playAudioFromBytes } from "../../modules/utils";
import { TrainingModals } from "../../components/TrainingModals/TrainingModals";
import { updateConversation } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";

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

  const { t } = useTranslation();

  useEffect(() => {
    setUser(loaderData.user);
  }, []);

  const [messages, setMessages] = useState(
    loaderData.conversation.messages as TMessage[]
  );

  useEffect(() => {
    const updateMessages = (
      chunk: string,
      agentSlug: string,
      prevMessages: TMessage[]
    ) => {
      const newMessages = [...prevMessages];
      const lastMessage = newMessages[newMessages.length - 1];

      if (lastMessage && lastMessage.type === "assistant") {
        if (lastMessage.agent_slug === agentSlug) {
          lastMessage.text += chunk;
        }
        const targetVersion = lastMessage.versions?.find(
          (v) => v.agent_slug === agentSlug
        );
        if (targetVersion) {
          targetVersion.text += chunk;
        } else {
          lastMessage.versions = [
            ...(lastMessage.versions || []),
            {
              text: chunk,
              type: "assistant",
              agent_slug: agentSlug,
            },
          ];
        }
      } else {
        const assistantMessage: TMessage = {
          type: "assistant",
          text: chunk,
          attachments: [],
          agent_slug: agentSlug,
        };
        assistantMessage.versions = [
          {
            text: chunk,
            type: "assistant",
            agent_slug: agentSlug,
          },
        ];
        newMessages.push(assistantMessage);
      }
      return newMessages;
    };

    const updateLastMessagesIds = (data, prevMessages) => {
      const newMessages = [...prevMessages];
      newMessages.reverse();

      const lastAIMessage = newMessages.find((m) => m.type === "assistant");
      if (lastAIMessage) {
        lastAIMessage.id = data.ai_message_id;
      }
      const lastUserMessage = newMessages.find((m) => m.type === "user");
      if (lastUserMessage) {
        lastUserMessage.id = data.user_message_id;
      }
      newMessages.reverse();
      return newMessages;
    };

    socket.on("response", (data) => {
      // setMessages(updateMessages(data.chunk, data.agent_slug));
      setMessages((prevMessages) =>
        updateMessages(data.chunk, data.agent_slug, prevMessages)
      );
    });
    socket.on("audio-file", (audioFile) => {
      playAudioFromBytes(audioFile);
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

  const onTitleEdit = async (title: string) => {
    if (!conversation?.id && !loaderData.conversation.id) return;

    // if
    await updateConversation(conversation?.id || loaderData.conversation.id, {
      title,
    });

    toast.success(t("title-updated"));
  };

  return (
    <>
      <TrainingModals />
      {chatState.isSidebarOpened && <Sidebar />}
      <div className="chat-container">
        <ChatHeader
          onTitleEdit={onTitleEdit}
          title={conversation?.title || loaderData.conversation.title || "Chat"}
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
                onGenerateSpeech={handleGenerateSpeech}
                onGenerateImage={handleGenerateImage}
              />
            ))}
        </div>
      </div>
    </>
  );
}
