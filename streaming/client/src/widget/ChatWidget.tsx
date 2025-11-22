import React, { useEffect, useState, useRef } from "react";
import { WidgetMessage } from "./WidgetMessage";
import { SimpleChatInput } from "./SimpleChatInput";
import { useWidgetStore, WidgetConfig } from "./widgetStore";
import { TMessage } from "../types/chatTypes";
import { TAgent } from "../types/agents";
import { initConversation, getAgents } from "../modules/apiCalls";
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
    updateMessage,
    setConversation,
    setAgents,
    setIsOpen,
  } = useWidgetStore();

  const chatMessageContainerRef = useRef<HTMLDivElement>(null);
  const [isInitialized, setIsInitialized] = useState(false);
  const initializationRef = useRef(false);
  const socketRef = useRef<SocketManager | null>(null);
  const [socketReady, setSocketReady] = useState(false);
  const streamingIndexRef = useRef<number | null>(null);
  const chunkHandlerRef = useRef<((data: any) => void) | null>(null);

  useEffect(() => {
    // Prevent multiple initializations
    if (initializationRef.current) {
      console.log("Widget: Initialization already in progress, skipping");
      return;
    }
    initializationRef.current = true;

    const initializeWidget = async () => {
      try {
        // Set auth token in localStorage for API calls
        localStorage.setItem("token", authToken);

        // Get user info to register with socket
        const getUser = async () => {
          try {
            const response = await fetch(`${API_URL}/v1/auth/user/me`, {
              headers: {
                Authorization: `Token ${authToken}`,
              },
            });
            if (response.ok) {
              return await response.json();
            }
          } catch (error) {
            console.error("Error fetching user:", error);
          }
          return null;
        };

        // Use streaming URL passed as prop (most reliable)
        // Fallback to window variable, then to default
        const streamingUrl =
          propStreamingUrl ||
          (window as any).WIDGET_STREAMING_URL ||
          (window.location.protocol === "https:" ? "https://" : "http://") +
            (window.location.hostname === "localhost" ||
            window.location.hostname === "127.0.0.1"
              ? window.location.hostname + ":8001"
              : window.location.host);

        console.log("Widget connecting to streaming server:", streamingUrl);
        console.log("Streaming URL sources:", {
          prop: propStreamingUrl,
          window: (window as any).WIDGET_STREAMING_URL,
          location: window.location.host,
        });
        const user = await getUser();
        const newSocket = new SocketManager(streamingUrl, user?.id);
        socketRef.current = newSocket;
        setSocketReady(true);
        
        // Register user with socket
        if (user?.id && newSocket) {
          newSocket.emit("register_user", user.id);
        }

        // Fetch agents and find the configured agent
        // Use the regular token (not public) since we're authenticating as the widget owner
        const agentsData = await getAgents(false);
        if (config.agent_slug && agentsData.agents) {
          const configuredAgent = agentsData.agents.find(
            (agent: TAgent) => agent.slug === config.agent_slug
          );
          if (configuredAgent) {
            setAgents([{ ...configuredAgent, selected: true }]);
          } else if (agentsData.agents.length > 0) {
            // Fallback to first public agent if configured agent not found
            setAgents(agentsData.agents.slice(0, 1).map((a: TAgent) => ({ ...a, selected: true })));
          }
        } else if (agentsData.agents && agentsData.agents.length > 0) {
          // Fallback to first public agent if no agent configured
          setAgents(agentsData.agents.slice(0, 1).map((a: TAgent) => ({ ...a, selected: true })));
        }

        // Initialize conversation
        // Use the regular token (not public) since we're authenticating as the widget owner
        const conv = await initConversation({ isPublic: false });
        setConversation(conv);
        setMessages(conv.messages || []);

        setIsInitialized(true);
      } catch (error) {
        console.error("Error initializing widget:", error);
        initializationRef.current = false; // Allow retry on error
      }
    };

    initializeWidget();

    return () => {
      if (socketRef.current) {
        console.log("Widget: Cleaning up socket on unmount");
        socketRef.current.disconnect();
        socketRef.current = null;
        setSocketReady(false);
      }
      initializationRef.current = false;
    };
  }, []); // Empty deps - only run once on mount

  useEffect(() => {
    if (!socketReady || !socketRef.current) {
      return;
    }

    const socketInstance = socketRef.current;

    const handleResponseFinished = (data: any) => {
      const currentMessages = useWidgetStore.getState().messages;
      const newMessages = JSON.parse(JSON.stringify(currentMessages));

      let aiIndex = -1;
      let userIndex = -1;

      for (let i = newMessages.length - 1; i >= 0; i--) {
        if (aiIndex === -1 && newMessages[i].type === "assistant") {
          aiIndex = i;
        }
        if (userIndex === -1 && newMessages[i].type === "user") {
          userIndex = i;
        }
        if (aiIndex !== -1 && userIndex !== -1) break;
      }

      if (aiIndex !== -1) {
        newMessages[aiIndex].id = data.ai_message_id;
        if (data.versions) {
          newMessages[aiIndex].versions = data.versions;
          if (data.versions.length > 0 && data.versions[0].text) {
            newMessages[aiIndex].text = data.versions[0].text;
          }
        }
      }

      if (userIndex !== -1) {
        const msg = newMessages[userIndex];
        if (!msg.text && currentMessages[userIndex]?.text) {
          msg.text = currentMessages[userIndex].text;
        }
        msg.id = data.user_message_id;
      }

      useWidgetStore.getState().setMessages(newMessages);

      if (streamingIndexRef.current !== null && chunkHandlerRef.current) {
        socketInstance.off(`response-for-${streamingIndexRef.current}`, chunkHandlerRef.current);
        streamingIndexRef.current = null;
        chunkHandlerRef.current = null;
      }
    };

    socketInstance.on("responseFinished", handleResponseFinished);

    return () => {
      socketInstance.off("responseFinished", handleResponseFinished);
      if (streamingIndexRef.current !== null && chunkHandlerRef.current) {
        socketInstance.off(`response-for-${streamingIndexRef.current}`, chunkHandlerRef.current);
        streamingIndexRef.current = null;
        chunkHandlerRef.current = null;
      }
    };
  }, [socketReady]);

  const scrollToBottom = () => {
    if (chatMessageContainerRef.current) {
      chatMessageContainerRef.current.scrollTop =
        chatMessageContainerRef.current.scrollHeight;
    }
  };

  const handleSendMessage = async (input: string): Promise<boolean> => {
    const socketInstance = socketRef.current;
    if (input.trim() === "" || !socketInstance || !conversation) return false;

    const selectedAgents = agents.filter((a) => a.selected);
    if (selectedAgents.length === 0) {
      return false;
    }

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
      versions: [
        {
          text: "",
          type: "assistant",
          agent_slug: selectedAgents[0].slug,
          agent_name: selectedAgents[0].name,
        },
      ],
    };

    useWidgetStore.getState().addMessage(userMessage);
    useWidgetStore.getState().addMessage(assistantMessage);

    const assistantIndex = useWidgetStore.getState().messages.length - 1;
    streamingIndexRef.current = assistantIndex;

    const handleChunk = (data: any) => {
      if (data.chunk) {
        const currentMessages = useWidgetStore.getState().messages;
        const msg = currentMessages[assistantIndex];
        if (msg && msg.type === "assistant") { // Ensure we are updating an assistant message
          const updatedText = (msg.text || "") + data.chunk;
          // Deep copy versions to avoid mutation issues
          const updatedVersions = msg.versions ? JSON.parse(JSON.stringify(msg.versions)) : [];
          if (updatedVersions.length > 0) {
            updatedVersions[updatedVersions.length - 1].text = updatedText;
          }
          
          useWidgetStore.getState().updateMessage(assistantIndex, {
            text: updatedText,
            versions: updatedVersions
          });
          scrollToBottom();
        }
      }
    };

    socketInstance.on(`response-for-${assistantIndex}`, handleChunk);
    chunkHandlerRef.current = handleChunk;

    try {
        const token = localStorage.getItem("token");
        console.log("Widget: Sending message via socket:", {
          message: userMessage.text,
          conversation_id: conversation.id,
          agent_slug: selectedAgents[0].slug,
        });

      socketInstance.emit("message", {
        message: {
          ...userMessage,
          agents: selectedAgents.map((a) => ({ slug: a.slug, name: a.name })),
        },
        context: useWidgetStore.getState().messages.slice(-20).map((m) => {
          const { attachments, ...rest } = m;
          const safeMessage = {
            ...rest,
            text: rest.text ?? "",
          };
          // Ensure assistant messages have versions array for the server
          if (safeMessage.type === "assistant" && !safeMessage.versions) {
            safeMessage.versions = safeMessage.agent_slug
              ? [
                  {
                    text: safeMessage.text || "",
                    type: "assistant",
                    agent_slug: safeMessage.agent_slug,
                    agent_name:
                      selectedAgents.find((a) => a.slug === safeMessage.agent_slug)?.name ||
                      safeMessage.agent_slug,
                  },
                ]
              : [];
          }
          return safeMessage;
        }),
        plugins: [],
        token: token,
        models_to_complete: selectedAgents,
        conversation: conversation,
        web_search_activated: config.web_search_enabled,
        specified_urls: [],
        use_rag: config.rag_enabled,
        multiagentic_modality: "isolated",
      });

      // scrollToBottom();
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
      {/* Chat Bubble Button */}
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

      {/* Chat Window */}
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
              disabled={!socketReady || !conversation}
            />
          </div>
        </div>
      )}
    </>
  );
};

export default ChatWidget;

