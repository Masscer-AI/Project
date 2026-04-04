import { create } from "zustand";
import { TMessage } from "../types/chatTypes";
import { TAgent } from "../types/agents";
import { TConversation } from "../types";
import { TWidgetCapability } from "../types";

export interface WidgetConfig {
  name: string;
  enabled: boolean;
  avatar_image: string;
  first_message: string;
  capabilities: TWidgetCapability[];
  style?: {
    primary_color?: string;
    theme?: "default" | "light" | "dark";
    show_history?: boolean;
  };
  agent_slug: string;
  agent_name: string;
}

interface WidgetStore {
  messages: TMessage[];
  conversation: TConversation | null;
  conversations: TConversation[];
  view: "list" | "chat";
  agents: TAgent[];
  config: WidgetConfig | null;
  authToken: string | null;
  widgetToken: string | null;
  isOpen: boolean;
  agentTaskStatus: string | null;
  setMessages: (messages: TMessage[]) => void;
  addMessage: (message: TMessage) => void;
  updateMessage: (index: number, message: Partial<TMessage>) => void;
  setConversation: (conversation: TConversation | null) => void;
  setConversations: (conversations: TConversation[]) => void;
  setView: (view: "list" | "chat") => void;
  setAgents: (agents: TAgent[]) => void;
  setConfig: (config: WidgetConfig) => void;
  setAuthToken: (token: string) => void;
  setWidgetToken: (token: string) => void;
  setIsOpen: (isOpen: boolean) => void;
  setAgentTaskStatus: (status: string | null) => void;
}

export const useWidgetStore = create<WidgetStore>()((set, get) => ({
  messages: [],
  conversation: null,
  conversations: [],
  view: "chat",
  agents: [],
  config: null,
  authToken: null,
  widgetToken: null,
  isOpen: false,
  agentTaskStatus: null,
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (index, message) =>
    set((state) => ({
      messages: state.messages.map((m, i) => (i === index ? { ...m, ...message } : m)),
    })),
  setConversation: (conversation) => set({ conversation }),
  setConversations: (conversations) => set({ conversations }),
  setView: (view) => set({ view }),
  setAgents: (agents) => set({ agents }),
  setConfig: (config) => set({ config }),
  setAuthToken: (authToken) => set({ authToken }),
  setWidgetToken: (widgetToken) => set({ widgetToken }),
  setIsOpen: (isOpen) => set({ isOpen }),
  setAgentTaskStatus: (agentTaskStatus) => set({ agentTaskStatus }),
}));

