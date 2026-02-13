import React, { useEffect } from "react";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";

// The Redis notification bridge wraps payloads as:
// { user_id, event_type, message: { ...actual_payload } }
// So we unwrap `data.message` to get the real event data.

type AgentEvent = {
  type: string;
  conversation_id: string;
  tool_name?: string;
  error?: string;
  [key: string]: unknown;
};

type AgentFinishedEvent = {
  conversation_id: string;
  output: string;
  message_id: number | null;
  iterations: number;
  tool_calls_count: number;
};

type RedisNotification<T> = {
  user_id: number;
  event_type: string;
  message: T;
};

/**
 * Listens for agent task events (agent_events_channel + agent_loop_finished)
 * and updates the store's agentTaskStatus so the Message component can display it.
 *
 * On agent_loop_finished, refreshes the conversation so the new message appears.
 * Renders nothing — purely a side-effect listener.
 */
export const AgentTaskListener = () => {
  const { t } = useTranslation();
  const { socket, conversation, setConversation, setAgentTaskStatus } =
    useStore((state) => ({
      socket: state.socket,
      conversation: state.conversation,
      setConversation: state.setConversation,
      setAgentTaskStatus: state.setAgentTaskStatus,
    }));

  useEffect(() => {
    const handleAgentEvent = (raw: RedisNotification<AgentEvent>) => {
      const data = raw.message;
      if (!data) return;

      // Only handle events for the current conversation
      if (!conversation?.id || data.conversation_id !== conversation.id) return;

      switch (data.type) {
        case "tool_call_start":
          setAgentTaskStatus(
            t("agent-running-tool", { toolName: data.tool_name || "..." })
          );
          break;
        case "tool_call_end":
          setAgentTaskStatus(
            t("agent-tool-completed", { toolName: data.tool_name || "..." })
          );
          break;
        case "loop_start":
        case "iteration_start":
          setAgentTaskStatus(t("agent-processing"));
          break;
        case "error":
          setAgentTaskStatus(null);
          break;
        default:
          break;
      }
    };

    const handleAgentFinished = (raw: RedisNotification<AgentFinishedEvent>) => {
      const data = raw.message;
      if (!data) return;

      if (!conversation?.id || data.conversation_id !== conversation.id) return;

      // Clear the status and refresh the conversation to load the new message
      setAgentTaskStatus(null);
      setConversation(conversation.id);
    };

    socket.on("agent_events_channel", handleAgentEvent);
    socket.on("agent_loop_finished", handleAgentFinished);

    return () => {
      socket.off("agent_events_channel", handleAgentEvent);
      socket.off("agent_loop_finished", handleAgentFinished);
    };
  }, [conversation, socket, setConversation, setAgentTaskStatus, t]);

  return null;
};
