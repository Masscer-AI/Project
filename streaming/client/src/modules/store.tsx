import { createWithEqualityFn as create } from "zustand/traditional";
import { TConversationData } from "../types/chatTypes";
import { getAgents, getConversation, initConversation } from "./apiCalls";
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

type Agent = {
  name: string;
  slug: string;
};

type Store = {
  messages: Message[];
  input: string;
  model: Model;
  models: Model[];
  agents: Agent[];
  chatState: {
    isSidebarOpened: boolean;
    attachments: TAttachment[];
    selectedAgent: string;
  };
  conversation: TConversationData | undefined;
  setMessages: (messages: Message[]) => void;
  setConversation: (conversationId: string | null) => void;
  addAttachment: (newAttachment: TAttachment) => void;
  setInput: (input: string) => void;
  setModel: (model: Model) => void;
  setModels: (models: Model[]) => void;
  fetchAgents: () => void;
  toggleSidebar: () => void;
  cleanAttachments: () => void;
  deleteAttachment: (index: number) => void;
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
  agents: [],
  chatState: { isSidebarOpened: false, attachments: [], selectedAgent: "" },
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
        ...state.chatState,
        attachments: [...state.chatState.attachments, newAttachment],
      },
    }));
  },
  fetchAgents: async () => {
    const agents = await getAgents();
    set({
      agents,
      chatState: {
        isSidebarOpened: false,
        attachments: [],
        selectedAgent: agents.length > 0 ? agents[0].slug : "",
      },
    });
  },
  toggleSidebar: () =>
    set((state) => ({
      chatState: {
        ...state.chatState,
        isSidebarOpened: !state.chatState.isSidebarOpened,
      },
    })),
  cleanAttachments: () =>
    set((state) => ({
      chatState: {
        ...state.chatState,
        attachments: [],
      },
    })),
  deleteAttachment: (index) => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        attachments: state.chatState.attachments.filter((_, i) => i !== index),
      },
    }));
  },
}));
