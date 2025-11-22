import { create } from "zustand";
import { TMessage } from "../types/chatTypes";
import { TAgent } from "../types/agents";
import { TConversation } from "../types";

export interface WidgetConfig {
  name: string;
  enabled: boolean;
  web_search_enabled: boolean;
  rag_enabled: boolean;
  plugins_enabled: string[];
  agent_slug: string;
  agent_name: string;
}

interface WidgetStore {
  messages: TMessage[];
  conversation: TConversation | null;
  agents: TAgent[];
  config: WidgetConfig | null;
  authToken: string | null;
  widgetToken: string | null;
  isOpen: boolean;
  setMessages: (messages: TMessage[]) => void;
  addMessage: (message: TMessage) => void;
  updateMessage: (index: number, message: Partial<TMessage>) => void;
  setConversation: (conversation: TConversation | null) => void;
  setAgents: (agents: TAgent[]) => void;
  setConfig: (config: WidgetConfig) => void;
  setAuthToken: (token: string) => void;
  setWidgetToken: (token: string) => void;
  setIsOpen: (isOpen: boolean) => void;
}

export const useWidgetStore = create<WidgetStore>()((set, get) => ({
  messages: [],
  conversation: null,
  agents: [],
  config: null,
  authToken: null,
  widgetToken: null,
  isOpen: false,
  setMessages: (messages) => set({ messages }),
  addMessage: (message) => set((state) => ({ messages: [...state.messages, message] })),
  updateMessage: (index, message) =>
    set((state) => ({
      messages: state.messages.map((m, i) => (i === index ? { ...m, ...message } : m)),
    })),
  setConversation: (conversation) => set({ conversation }),
  setAgents: (agents) => set({ agents }),
  setConfig: (config) => set({ config }),
  setAuthToken: (authToken) => set({ authToken }),
  setWidgetToken: (widgetToken) => set({ widgetToken }),
  setIsOpen: (isOpen) => set({ isOpen }),
}));

