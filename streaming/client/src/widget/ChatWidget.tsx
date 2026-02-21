import React, { useEffect, useState, useRef } from "react";
import { WidgetMessage } from "./WidgetMessage";
import { SimpleChatInput } from "./SimpleChatInput";
import { useWidgetStore, WidgetConfig } from "./widgetStore";
import { TMessage } from "../types/chatTypes";
import { TAgent } from "../types/agents";
import { TVersion } from "../types";
import { initConversation, getAgents, triggerAgentTask } from "../modules/apiCalls";
import { SocketManager } from "../modules/socketManager";
import { API_URL } from "../modules/constants";
import "./ChatWidget.css";
import "./WidgetMessage.css";

interface ChatWidgetProps {
  config: WidgetConfig;
  authToken: string;
  widgetToken: string;
  streamingUrl: string;
}

const ChatWidget: React.FC<ChatWidgetProps> = ({
  config,
  authToken,
  widgetToken,
  streamingUrl: propStreamingUrl,
}) => {
  const {
    messages,
    conversation,
    agents,
    isOpen,
    setMessages,
    addMessage,
    setConversation,
    setAgents,
    setIsOpen,
  } = useWidgetStore();

  const chatMessageContainerRef = useRef<HTMLDivElement>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const initializationRef = useRef(false);
  const socketRef = useRef<SocketManager | null>(null);
  const [socketReady, setSocketReady] = useState(false);

  useEffect(() => {
    if (initializationRef.current) return;
    initializationRef.current = true;

    const initializeWidget = async () => {
      try {
        localStorage.setItem("token", authToken);

        const getUser = async () => {
          try {
            const response = await fetch(`${API_URL}/v1/auth/user/me`, {
              headers: { Authorization: `Token ${authToken}` },
            });
            if (response.ok) return await response.json();
          } catch (error) {
            console.error("Error fetching user:", error);
          }
          return null;
        };

        const streamingUrl =
          propStreamingUrl ||
          (window as any).WIDGET_STREAMING_URL ||
          (window.location.protocol === "https:" ? "https://" : "http://") +
            (window.location.hostname === "localhost" ||
            window.location.hostname === "127.0.0.1"
              ? window.location.hostname + ":8001"
              : window.location.host);

        const user = await getUser();
        const newSocket = new SocketManager(streamingUrl, user?.id);
        socketRef.current = newSocket;
        setSocketReady(true);

        if (user?.id && newSocket) {
          newSocket.emit("register_user", user.id);
        }

        const agentsData = await getAgents(false);
        if (config.agent_slug && agentsData.agents) {
          const configuredAgent = agentsData.agents.find(
            (agent: TAgent) => agent.slug === config.agent_slug
          );
          if (configuredAgent) {
            setAgents([{ ...configuredAgent, selected: true }]);
          } else if (agentsData.agents.length > 0) {
            setAgents(agentsData.agents.slice(0, 1).map((a: TAgent) => ({ ...a, selected: true })));
          }
        } else if (agentsData.agents && agentsData.agents.length > 0) {
          setAgents(agentsData.agents.slice(0, 1).map((a: TAgent) => ({ ...a, selected: true })));
        }

        const conv = await initConversation({ isPublic: false });
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

    const selectedAgents = agents.filter((a) => a.selected);
    if (selectedAgents.length === 0) return false;

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
      agent_slug: selectedAgents[0].slug,
      versions: [{
        text: "",
        type: "assistant",
        agent_slug: selectedAgents[0].slug,
        agent_name: selectedAgents[0].name,
      }],
    };

    useWidgetStore.getState().addMessage(userMessage);
    useWidgetStore.getState().addMessage(assistantMessage);

    try {
      const toolNames = ["read_attachment", "list_attachments"];
      if (config.web_search_enabled) toolNames.push("explore_web");
      if (config.rag_enabled) toolNames.push("rag_query");

      await triggerAgentTask({
        conversation_id: conversation.id,
        agent_slugs: selectedAgents.map((a) => a.slug),
        user_inputs: [{ type: "input_text", text: input }],
        tool_names: toolNames,
        multiagentic_modality: "isolated",
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
        <div className="chat-widget-container">
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
