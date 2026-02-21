import React, { useEffect, useState } from "react";

import { Message } from "../../components/Message/Message";

import { useLoaderData } from "react-router-dom";

import { useStore } from "../../modules/store";
import { TChatLoader, TMessage } from "../../types/chatTypes";

import { useTranslation } from "react-i18next";
import { TVersion } from "../../types";
import toast from "react-hot-toast";
import { triggerAgentTask } from "../../modules/apiCalls";

export default function SharedChatView() {
  const loaderData = useLoaderData() as TChatLoader;

  const {
    conversation,
    socket,
    setUser,
    agents,
    startup,
    setConversation,
  } = useStore((state) => ({
    socket: state.socket,
    conversation: state.conversation,
    setUser: state.setUser,
    agents: state.agents,
    startup: state.startup,
    setConversation: state.setConversation,
  }));

  const { t } = useTranslation();

  useEffect(() => {
    setUser(loaderData.user);
    startup();
    if (loaderData.conversation) {
      setConversation(loaderData.conversation.id);
    }
  }, []);

  const [messages, setMessages] = useState(
    loaderData.conversation.messages as TMessage[]
  );

  useEffect(() => {
    const handleAgentEvents = (raw: {
      user_id?: number;
      message?: { type: string; conversation_id?: string; version?: TVersion };
    }) => {
      const data = raw?.message;
      const conv = conversation ?? loaderData.conversation;
      if (!data || !conv?.id || data.conversation_id !== conv.id) return;
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
          updated[updated.length - 1] = {
            ...last,
            versions,
            text: versions[0]?.text ?? last.text,
          };
          return updated;
        });
      }
    };

    const handleAgentFinished = (raw: {
      user_id?: number;
      message?: {
        type: string;
        conversation_id?: string;
        user_message_id?: number;
        ai_message_id?: number;
        versions?: TVersion[];
        next_agent_slug?: string;
      };
    }) => {
      const data = raw?.message;
      const conv = conversation ?? loaderData.conversation;
      if (!data || !conv?.id || data.conversation_id !== conv.id) return;

      if (data.type === "agent_loop_finished") {
        setMessages((prev) => {
          const newMessages = [...prev];
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].type === "assistant") {
              if (data.ai_message_id) newMessages[i].id = data.ai_message_id;
              if (data.versions) {
                newMessages[i].versions = data.versions;
                if (data.versions.length > 0 && data.versions[0].text) {
                  newMessages[i].text = data.versions[0].text;
                }
              }
              break;
            }
          }
          for (let i = newMessages.length - 1; i >= 0; i--) {
            if (newMessages[i].type === "user") {
              if (data.user_message_id) newMessages[i].id = data.user_message_id;
              break;
            }
          }
          return newMessages;
        });
      }
    };

    socket.on("agent_events_channel", handleAgentEvents);
    socket.on("agent_loop_finished", handleAgentFinished);

    return () => {
      socket.off("agent_events_channel", handleAgentEvents);
      socket.off("agent_loop_finished", handleAgentFinished);
    };
  }, [conversation?.id]);

  useEffect(() => {
    if (!conversation?.messages) return;
    setMessages(conversation?.messages);
  }, [conversation]);

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
      await triggerAgentTask({
        conversation_id: currentConversation.id,
        agent_slugs: selectedAgents.map((a) => a.slug),
        user_inputs: [{ type: "input_text", text: newText }],
        tool_names: ["read_attachment", "list_attachments"],
        regenerate_message_id: userMessage.id,
      });
    } catch (error) {
      console.error("Error regenerating via agent task:", error);
      toast.error(t("agent-task-failed"));
    }
  };

  const onMessageEdit = (
    index: number,
    text: string,
    versions?: TVersion[]
  ) => {
    const message = messages[index];
    if (!message) return;

    if (message.type === "user" && message.id) {
      handleRegenerateAgentTask(message, index, text);
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
