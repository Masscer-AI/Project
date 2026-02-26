import React, { useEffect, useState, useRef } from "react";
import { WidgetMessage } from "./WidgetMessage";
import { SimpleChatInput } from "./SimpleChatInput";
import { useWidgetStore, WidgetConfig } from "./widgetStore";
import { TMessage } from "../types/chatTypes";
import { TVersion } from "../types";
import {
  initWidgetConversation,
  triggerWidgetAgentTask,
  getWidgetSocketRoute,
} from "../modules/apiCalls";
import { SocketManager } from "../modules/socketManager";
import "./ChatWidget.css";
import "./WidgetMessage.css";

interface ChatWidgetProps {
  config: WidgetConfig;
  sessionToken: string;
  widgetToken: string;
  streamingUrl: string;
}

const ChatWidget: React.FC<ChatWidgetProps> = ({
  config,
  sessionToken,
  widgetToken,
  streamingUrl: propStreamingUrl,
}) => {
  const {
    messages,
    conversation,
    isOpen,
    setMessages,
    setConversation,
    setIsOpen,
  } = useWidgetStore();

  const chatMessageContainerRef = useRef<HTMLDivElement>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const initializationRef = useRef(false);
  const socketRef = useRef<SocketManager | null>(null);
  const [socketReady, setSocketReady] = useState(false);
  const widgetTheme = config.style?.theme ?? "default";
  const isDarkTheme = widgetTheme === "dark";
  const widgetPrimaryColor = config.style?.primary_color?.trim();
  const widgetCssVars = {
    "--widget-primary":
      widgetPrimaryColor && widgetPrimaryColor.length > 0
        ? widgetPrimaryColor
        : "#000000",
    "--widget-bg": isDarkTheme ? "#111827" : "#ffffff",
    "--widget-input-bg": isDarkTheme ? "#0f172a" : "#f8f9fa",
    "--widget-input-focus-bg": isDarkTheme ? "#111827" : "#ffffff",
    "--widget-border": isDarkTheme
      ? "rgba(255, 255, 255, 0.12)"
      : "rgba(0, 0, 0, 0.08)",
    "--widget-input-border": isDarkTheme
      ? "rgba(255, 255, 255, 0.2)"
      : "rgba(0, 0, 0, 0.1)",
    "--widget-scrollbar-thumb": isDarkTheme
      ? "rgba(255, 255, 255, 0.2)"
      : "rgba(0, 0, 0, 0.1)",
    "--widget-scrollbar-thumb-hover": isDarkTheme
      ? "rgba(255, 255, 255, 0.28)"
      : "rgba(0, 0, 0, 0.15)",
    "--widget-text": isDarkTheme ? "#e5e7eb" : "#333333",
    "--widget-muted": isDarkTheme ? "#9ca3af" : "#666666",
    "--widget-placeholder": isDarkTheme ? "#9ca3af" : "#999999",
    "--widget-assistant-bg": isDarkTheme ? "#1f2937" : "#f0f0f0",
    "--widget-assistant-text": isDarkTheme ? "#e5e7eb" : "#333333",
    "--widget-code-bg": isDarkTheme
      ? "rgba(255, 255, 255, 0.12)"
      : "rgba(0, 0, 0, 0.1)",
    "--widget-pre-bg": isDarkTheme
      ? "rgba(255, 255, 255, 0.06)"
      : "rgba(0, 0, 0, 0.05)",
    "--widget-table-border": isDarkTheme ? "#374151" : "#dddddd",
    "--widget-table-header-bg": isDarkTheme ? "#111827" : "#f5f5f5",
    "--widget-link": isDarkTheme ? "#60a5fa" : "#007bff",
    "--widget-blockquote-border": isDarkTheme ? "#4b5563" : "#cccccc",
    "--widget-focus-ring": isDarkTheme
      ? "rgba(255, 255, 255, 0.16)"
      : "rgba(0, 0, 0, 0.1)",
  } as React.CSSProperties;

  useEffect(() => {
    if (initializationRef.current) return;
    initializationRef.current = true;

    const initializeWidget = async () => {
      try {
        localStorage.setItem(
          `masscer_widget_session_${widgetToken}`,
          sessionToken
        );

        const streamingUrl =
          propStreamingUrl ||
          (window as any).WIDGET_STREAMING_URL ||
          (window.location.protocol === "https:" ? "https://" : "http://") +
            (window.location.hostname === "localhost" ||
            window.location.hostname === "127.0.0.1"
              ? window.location.hostname + ":8001"
              : window.location.host);

        const newSocket = new SocketManager(streamingUrl);
        socketRef.current = newSocket;
        setSocketReady(true);

        if (newSocket) {
          const socketRoute = await getWidgetSocketRoute(widgetToken, sessionToken);
          newSocket.registerWidgetSession(socketRoute.route_key);
        }

        const conv = await initWidgetConversation(widgetToken, sessionToken);
        setConversation(conv);
        setMessages(conv.messages || []);

        setIsInitialized(true);
      } catch (error) {
        console.error("Error initializing widget:", error);
        initializationRef.current = false;
      }
    };

    initializeWidget();

    return () => {
      if (socketRef.current) {
        socketRef.current.disconnect();
        socketRef.current = null;
        setSocketReady(false);
      }
      initializationRef.current = false;
    };
  }, []);

  useEffect(() => {
    if (!socketReady || !socketRef.current) return;

    const socketInstance = socketRef.current;

    const handleAgentEvents = (raw: {
      user_id?: number;
      message?: { type: string; conversation_id?: string; version?: TVersion };
    }) => {
      const data = raw?.message;
      const conv = useWidgetStore.getState().conversation;
      if (!data || !conv?.id || data.conversation_id !== conv.id) return;

      if (data.type === "agent_version_ready" && data.version) {
        const currentMessages = useWidgetStore.getState().messages;
        const newMessages = [...currentMessages];
        const last = newMessages[newMessages.length - 1];
        if (!last || last.type !== "assistant") return;

        const versions = [...(last.versions || [])];
        const existingIdx = versions.findIndex(
          (v) => v.agent_slug === data.version!.agent_slug
        );
        if (existingIdx >= 0) versions[existingIdx] = data.version!;
        else versions.push(data.version!);

        newMessages[newMessages.length - 1] = {
          ...last,
          versions,
          text: versions[0]?.text ?? last.text,
        };
        useWidgetStore.getState().setMessages(newMessages);
        scrollToBottom();
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
      const conv = useWidgetStore.getState().conversation;
      if (!data || !conv?.id || data.conversation_id !== conv.id) return;

      if (data.type === "agent_loop_finished") {
        const currentMessages = useWidgetStore.getState().messages;
        const newMessages = [...currentMessages];

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

        useWidgetStore.getState().setMessages(newMessages);

        if (data.next_agent_slug) {
          useWidgetStore.getState().addMessage({
            type: "assistant",
            text: "",
            attachments: [],
            agent_slug: data.next_agent_slug,
            versions: [{
              text: "",
              type: "assistant",
              agent_slug: data.next_agent_slug,
              agent_name: data.next_agent_slug,
            }],
          });
        }
      }
    };

    socketInstance.on("agent_events_channel", handleAgentEvents);
    socketInstance.on("agent_loop_finished", handleAgentFinished);

    return () => {
      socketInstance.off("agent_events_channel", handleAgentEvents);
      socketInstance.off("agent_loop_finished", handleAgentFinished);
    };
  }, [socketReady]);

  const scrollToBottom = () => {
    if (chatMessageContainerRef.current) {
      chatMessageContainerRef.current.scrollTop =
        chatMessageContainerRef.current.scrollHeight;
    }
  };

  const handleSendMessage = async (input: string): Promise<boolean> => {
    if (input.trim() === "" || !conversation) return false;
    const agentSlug = config.agent_slug || "widget-agent";
    const agentName = config.agent_name || "Assistant";

    const userMessage: TMessage = {
      type: "user",
      text: input,
      attachments: [],
      index: useWidgetStore.getState().messages.length,
    };

    const assistantMessage: TMessage = {
      type: "assistant",
      text: "",
      attachments: [],
      agent_slug: agentSlug,
      versions: [{
        text: "",
        type: "assistant",
        agent_slug: agentSlug,
        agent_name: agentName,
      }],
    };

    useWidgetStore.getState().addMessage(userMessage);
    useWidgetStore.getState().addMessage(assistantMessage);

    try {
      await triggerWidgetAgentTask(widgetToken, sessionToken, {
        conversation_id: conversation.id,
        user_inputs: [{ type: "input_text", text: input }],
      });

      scrollToBottom();
      return true;
    } catch (error) {
      console.error("Error sending message:", error);
      return false;
    }
  };

  if (!isInitialized) {
    return (
      <div className="chat-widget-loading">
        <div className="loading-spinner">Loading...</div>
      </div>
    );
  }

  return (
    <>
      {!isOpen && (
        <button
          className="chat-widget-bubble"
          style={widgetCssVars}
          onClick={() => setIsOpen(true)}
          aria-label="Open chat"
        >
          <svg
            width="24"
            height="24"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
          </svg>
        </button>
      )}

      {isOpen && (
        <div className="chat-widget-container" style={widgetCssVars}>
          <div className="chat-widget-header">
            <h3>{config.name || "Chat"}</h3>
            <button
              className="chat-widget-close"
              onClick={() => setIsOpen(false)}
              aria-label="Close chat"
            >
              ×
            </button>
          </div>
          <div ref={chatMessageContainerRef} className="chat-widget-messages">
            {messages.map((msg, index) => (
              <WidgetMessage
                {...msg}
                key={msg.id ?? `${index}-${msg.type}`}
                index={index}
                numberMessages={messages.length}
              />
            ))}
          </div>
          <div className="chat-widget-input-container">
            <SimpleChatInput
              onSendMessage={handleSendMessage}
              disabled={!conversation}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default ChatWidget;
