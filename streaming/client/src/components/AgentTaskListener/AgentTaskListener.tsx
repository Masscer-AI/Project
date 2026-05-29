import React, { useEffect, useRef } from "react";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { showOrganizationBillingBlockedToast } from "../../utils/organizationBillingToast";

const TOOL_STATUS_MIN_MS = 1500; // Keep tool call status visible so user notices the AI invoked a function

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
  next_agent_slug?: string;
  /** Present when the agent loop ended without saving an assistant message (e.g. org billing). */
  status?: string;
  error?: string;
  billing_reason?: string;
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
 * Tool call status is kept visible for TOOL_STATUS_MIN_MS so users notice function invocations.
 * On agent_loop_finished, refreshes the conversation so the new message appears.
 * Renders nothing — purely a side-effect listener.
 */
export const AgentTaskListener = () => {
  const { t } = useTranslation();
  const {
    socket,
    conversation,
    setConversation,
    setAgentTaskStatus,
    pushAgentTaskEvent,
    clearAgentTaskEvents,
  } = useStore((state) => ({
    socket: state.socket,
    conversation: state.conversation,
    setConversation: state.setConversation,
    setAgentTaskStatus: state.setAgentTaskStatus,
    pushAgentTaskEvent: state.pushAgentTaskEvent,
    clearAgentTaskEvents: state.clearAgentTaskEvents,
  }));

  const toolHoldRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingStatusRef = useRef<string | null>(null);

  useEffect(() => {
    const applyStatus = (status: string | null, isToolEvent: boolean) => {
      if (isToolEvent) {
        if (toolHoldRef.current) clearTimeout(toolHoldRef.current);
        setAgentTaskStatus(status);
        pendingStatusRef.current = null;
        toolHoldRef.current = setTimeout(() => {
          toolHoldRef.current = null;
          if (pendingStatusRef.current !== null) {
            setAgentTaskStatus(pendingStatusRef.current);
            pendingStatusRef.current = null;
          }
        }, TOOL_STATUS_MIN_MS);
      } else {
        if (toolHoldRef.current) {
          pendingStatusRef.current = status;
        } else {
          setAgentTaskStatus(status);
        }
      }
    };

    const handleAgentEvent = (raw: RedisNotification<AgentEvent>) => {
      const data = raw.message;
      if (!data) return;

      if (!conversation?.id || data.conversation_id !== conversation.id) return;

      // Accumulate the full live timeline so the user can expand all steps.
      pushAgentTaskEvent({
        type: data.type,
        tool_name: (data.tool_name as string) || null,
        iteration: (data.iteration as number) ?? null,
        duration: (data.duration as number) ?? null,
        error: (data.error as string) || null,
        ts: new Date().toISOString(),
      });

      switch (data.type) {
        case "tool_call_start":
          applyStatus(
            t("agent-running-tool", { toolName: data.tool_name || "..." }),
            true
          );
          break;
        case "tool_call_end":
          applyStatus(
            t("agent-tool-completed", { toolName: data.tool_name || "..." }),
            true
          );
          break;
        case "loop_start":
        case "iteration_start":
          applyStatus(t("agent-processing"), false);
          break;
        case "agent_complete": {
          const total = data.total as number | undefined;
          const index = data.index as number | undefined;
          const agentName = (data.agent_name as string) || "...";
          const status =
            total != null && total > 1 && index != null && index < total
              ? t("agent-response-complete-progress", {
                  agentName,
                  index: String(index),
                  total: String(total),
                })
              : t("agent-response-complete", { agentName });
          applyStatus(status, false);
          break;
        }
        case "error":
          if (toolHoldRef.current) {
            clearTimeout(toolHoldRef.current);
            toolHoldRef.current = null;
            pendingStatusRef.current = null;
          }
          setAgentTaskStatus(null);
          clearAgentTaskEvents();
          break;
        default:
          break;
      }
    };

    const handleAgentFinished = (raw: RedisNotification<AgentFinishedEvent>) => {
      const data = raw.message;
      if (!data) return;

      if (!conversation?.id || data.conversation_id !== conversation.id) return;

      if (data.next_agent_slug) {
        setConversation(conversation.id);
        return;
      }

      if (
        data.status === "error" &&
        data.error === "organization_billing_blocked"
      ) {
        if (toolHoldRef.current) {
          clearTimeout(toolHoldRef.current);
          toolHoldRef.current = null;
          pendingStatusRef.current = null;
        }
        showOrganizationBillingBlockedToast(
          typeof data.billing_reason === "string"
            ? data.billing_reason
            : undefined
        );
        setAgentTaskStatus(null);
        clearAgentTaskEvents();
        void setConversation(conversation.id);
        return;
      }

      if (toolHoldRef.current) {
        clearTimeout(toolHoldRef.current);
        toolHoldRef.current = null;
        pendingStatusRef.current = null;
      }
      setAgentTaskStatus(null);
      // Live timeline is no longer needed: the saved message exposes the
      // persisted event_log through the execution log modal.
      clearAgentTaskEvents();
      setConversation(conversation.id);
    };

    socket.on("agent_events_channel", handleAgentEvent);
    socket.on("agent_loop_finished", handleAgentFinished);

    return () => {
      socket.off("agent_events_channel", handleAgentEvent);
      socket.off("agent_loop_finished", handleAgentFinished);
      if (toolHoldRef.current) {
        clearTimeout(toolHoldRef.current);
        toolHoldRef.current = null;
      }
      pendingStatusRef.current = null;
    };
  }, [
    conversation,
    socket,
    setConversation,
    setAgentTaskStatus,
    pushAgentTaskEvent,
    clearAgentTaskEvents,
    t,
  ]);

  return null;
};
