
import { createWithEqualityFn as create } from 'zustand/traditional'

import { TConversationData } from "../types/chatTypes";
import { getConversation } from "./apiCalls";

type Message = {
  sender: string;
  text: string;
  imageUrl?: string;
};

type Model = {
  name: string;
  provider: string;
};

type Store = {
  count: number;
  messages: Message[];
  input: string;
  model: Model;
  models: Model[];
  chatState: { isSidebarOpened: boolean };
  conversation: TConversationData | undefined;
  inc: () => void;
  setMessages: (messages: Message[]) => void;
  setConversation: (conversationId: string) => void;

  setInput: (input: string) => void;
  setModel: (model: Model) => void;
  setModels: (models: Model[]) => void;
  toggleSidebar: () => void;
};

export const useStore = create<Store>()((set) => ({
  count: 1,
  messages: [],
  input: "",
  model: { name: "gpt-4o", provider: "openai" },
  models: [
    { name: "gpt-4o", provider: "openai" },
    { name: "gpt-4o-mini", provider: "openai" },
    { name: "claude-3-5-sonnet-20240620", provider: "anthropic" },
    // { name: "claude-3-opus-20240229", provider: "anthropic" },
    // { name: "claude-3-haiku-20240307", provider: "anthropic" },
  ],
  chatState: { isSidebarOpened: false },
  conversation: undefined,
  setConversation: async (conversationId) => {
    const data = await getConversation(conversationId);
    set(() => ({
      conversation: data,
    }));
  },
  inc: () => set((state) => ({ count: state.count + 1 })),
  setMessages: (messages) => set({ messages }),
  setInput: (input) => set({ input }),
  setModel: (model) => set({ model }),
  setModels: (models) => set({ models }),
  toggleSidebar: () =>
    set((state) => ({
      chatState: { isSidebarOpened: !state.chatState.isSidebarOpened },
    })),
}));
