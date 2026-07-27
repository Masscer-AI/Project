import React, { useEffect, useRef } from "react";
import { useStore } from "../../modules/store";
import { getAgentTaskStatus } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { showOrganizationBillingBlockedToast } from "../../utils/organizationBillingToast";
import { useLocalizedToolName } from "../../utils/localizedToolName";
import { playNotificationSound } from "../../utils/notificationSound";

const TOOL_STATUS_MIN_MS = 1500; // Keep tool call status visible so user notices the AI invoked a function
const AGENT_TASK_POLL_INTERVAL_MS = 3000;
const AGENT_TASK_POLL_FIRST_MS = 4000;
/** Don't clear from "inactive" until we've seen active:true, or this grace elapsed (enqueue race). */
const AGENT_TASK_POLL_INACTIVE_GRACE_MS = 15000;

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
 * Also polls task status as a fallback when websocket finish events are missed.
 * Renders nothing — purely a side-effect listener.
 */
export const AgentTaskListener = () => {
  const { t } = useTranslation();
  const localizeTool = useLocalizedToolName();
  const {
    socket,
    setConversation,
    setAgentTaskStatus,
    pushAgentTaskEvent,
    clearAgentTaskEvents,
    agentTaskStatus,
    agentTaskConversationId,
  } = useStore((state) => ({
    socket: state.socket,
    setConversation: state.setConversation,
    setAgentTaskStatus: state.setAgentTaskStatus,
    pushAgentTaskEvent: state.pushAgentTaskEvent,
    clearAgentTaskEvents: state.clearAgentTaskEvents,
    agentTaskStatus: state.agentTaskStatus,
    agentTaskConversationId: state.agentTaskConversationId,
  }));

  const toolHoldRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingStatusRef = useRef<string | null>(null);

  useEffect(() => {
    const eventBelongsToTrackedTask = (eventConversationId: string) => {
      const trackedId = useStore.getState().agentTaskConversationId;
      const currentId = useStore.getState().conversation?.id;
      if (trackedId) return eventConversationId === trackedId;
      return !!currentId && eventConversationId === currentId;
    };

    const clearToolHold = () => {
      if (toolHoldRef.current) {
        clearTimeout(toolHoldRef.current);
        toolHoldRef.current = null;
        pendingStatusRef.current = null;
      }
    };

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

      if (!eventBelongsToTrackedTask(data.conversation_id)) return;

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
            t("agent-running-tool", {
              toolName: localizeTool(data.tool_name as string | undefined),
            }),
            true
          );
          break;
        case "tool_call_end":
          applyStatus(
            t("agent-tool-completed", {
              toolName: localizeTool(data.tool_name as string | undefined),
            }),
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
          clearToolHold();
          playNotificationSound("error");
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

      if (!eventBelongsToTrackedTask(data.conversation_id)) return;

      const viewingThisConversation =
        useStore.getState().conversation?.id === data.conversation_id;

      if (data.next_agent_slug) {
        if (viewingThisConversation) {
          setConversation(data.conversation_id);
        }
        return;
      }

      if (data.status === "cancelled") {
        clearToolHold();
        setAgentTaskStatus(null);
        clearAgentTaskEvents();
        if (viewingThisConversation) {
          void setConversation(data.conversation_id);
        }
        return;
      }

      if (data.status === "error") {
        clearToolHold();
        playNotificationSound("error");
        if (data.error === "organization_billing_blocked") {
          showOrganizationBillingBlockedToast(
            typeof data.billing_reason === "string"
              ? data.billing_reason
              : undefined
          );
        }
        setAgentTaskStatus(null);
        clearAgentTaskEvents();
        if (viewingThisConversation) {
          void setConversation(data.conversation_id);
        }
        return;
      }

      clearToolHold();
      playNotificationSound("success");
      setAgentTaskStatus(null);
      // Live timeline is no longer needed: the saved message exposes the
      // persisted event_log through the execution log modal.
      clearAgentTaskEvents();
      if (viewingThisConversation) {
        setConversation(data.conversation_id);
      }
    };

    socket.on("agent_events_channel", handleAgentEvent);
    socket.on("agent_loop_finished", handleAgentFinished);

    return () => {
      socket.off("agent_events_channel", handleAgentEvent);
      socket.off("agent_loop_finished", handleAgentFinished);
      clearToolHold();
    };
  }, [
    socket,
    setConversation,
    setAgentTaskStatus,
    pushAgentTaskEvent,
    clearAgentTaskEvents,
    t,
    localizeTool,
  ]);

  // Polling fallback: clear stuck stop when the server says the task is done.
  useEffect(() => {
    if (!agentTaskStatus || !agentTaskConversationId) return;

    let cancelled = false;
    let sawActive = false;
    const startedAt = Date.now();
    const trackedConversationId = agentTaskConversationId;

    const tick = async () => {
      try {
        const res = await getAgentTaskStatus(trackedConversationId);
        if (cancelled) return;

        if (res.active) {
          sawActive = true;
          return;
        }

        const elapsed = Date.now() - startedAt;
        if (!sawActive && elapsed < AGENT_TASK_POLL_INACTIVE_GRACE_MS) {
          return;
        }

        if (toolHoldRef.current) {
          clearTimeout(toolHoldRef.current);
          toolHoldRef.current = null;
          pendingStatusRef.current = null;
        }
        setAgentTaskStatus(null);
        clearAgentTaskEvents();
        const currentId = useStore.getState().conversation?.id;
        if (currentId === trackedConversationId) {
          void setConversation(trackedConversationId);
        }
      } catch {
        // Ignore transient poll errors; websocket path or next tick may recover.
      }
    };

    const firstTimer = setTimeout(tick, AGENT_TASK_POLL_FIRST_MS);
    const intervalId = setInterval(tick, AGENT_TASK_POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      clearTimeout(firstTimer);
      clearInterval(intervalId);
    };
  }, [
    agentTaskStatus,
    agentTaskConversationId,
    setAgentTaskStatus,
    clearAgentTaskEvents,
    setConversation,
  ]);

  return null;
};
