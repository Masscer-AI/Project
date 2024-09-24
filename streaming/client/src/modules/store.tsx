import { createWithEqualityFn as create } from "zustand/traditional";

import { TConversationData } from "../types/chatTypes";
import { getConversation, initConversation } from "./apiCalls";
import { TAttachment } from "../types";

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
  messages: Message[];
  input: string;
  model: Model;
  models: Model[];
  chatState: { isSidebarOpened: boolean; attachments: TAttachment[] };
  conversation: TConversationData | undefined;
  setMessages: (messages: Message[]) => void;
  setConversation: (conversationId: string | null) => void;
  addAttachment: (newAttachment: TAttachment) => void;
  setInput: (input: string) => void;
  setModel: (model: Model) => void;
  setModels: (models: Model[]) => void;
  toggleSidebar: () => void;
  cleanAttachments: () => void; // Add this line
};

export const useStore = create<Store>()((set) => ({
  messages: [],
  input: "",
  model: { name: "gpt-4o", provider: "openai" },
  models: [
    { name: "gpt-4o", provider: "openai" },
    { name: "gpt-4o-mini", provider: "openai" },
    { name: "claude-3-5-sonnet-20240620", provider: "anthropic" },
  ],
  chatState: { isSidebarOpened: false, attachments: [] },
  conversation: undefined,
  setConversation: async (conversationId) => {
    let data;

    if (!conversationId) {
      data = await initConversation({ isPublic: false });
    } else {
      data = await getConversation(conversationId);
    }

    set(() => ({
      conversation: data,
    }));
  },
  setMessages: (messages) => set({ messages }),
  setInput: (input) => set({ input }),
  setModel: (model) => set({ model }),
  setModels: (models) => set({ models }),
  addAttachment: (newAttachment) => {
    set((state) => ({
      chatState: {
        isSidebarOpened: state.chatState.isSidebarOpened,
        attachments: [...state.chatState.attachments, newAttachment],
      },
    }));
  },
  toggleSidebar: () =>
    set((state) => ({
      chatState: {
        isSidebarOpened: !state.chatState.isSidebarOpened,
        attachments: [...state.chatState.attachments],
      },
    })),
  cleanAttachments: () =>
    set((state) => ({
      chatState: {
        ...state.chatState,
        attachments: [],
      },
    })),
}));
