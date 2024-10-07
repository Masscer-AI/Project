import { createWithEqualityFn as create } from "zustand/traditional";
import { TConversationData } from "../types/chatTypes";
import {
  getAgents,
  getConversation,
  initConversation,
  uploadDocument,
} from "./apiCalls";
import { TAttachment } from "../types";
import { SocketManager } from "./socketManager";
import { STREAMING_BACKEND_URL } from "./constants";

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
  socket: any;
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
  addAttachment: (newAttachment: TAttachment, conversation_id: string) => void;
  setInput: (input: string) => void;
  setModel: (model: Model) => void;
  setModels: (models: Model[]) => void;
  fetchAgents: () => void;
  toggleSidebar: () => void;
  cleanAttachments: () => void;
  deleteAttachment: (index: number) => void;
};

export const useStore = create<Store>()((set, get) => ({
  socket: new SocketManager(STREAMING_BACKEND_URL),
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
  addAttachment: async (newAttachment, conversation_id) => {
    const { chatState } = get();
    const formData = new FormData();

    formData.append("agent_slug", chatState.selectedAgent);
    formData.append("name", newAttachment.name);
    formData.append("conversation_id", String(conversation_id));
    // @ts-ignore
    formData.append("file", newAttachment.file);
    try {
      const r = await uploadDocument(formData);
      newAttachment.id = r.id
      set((state) => ({
        chatState: {
          ...state.chatState,
          attachments: [...state.chatState.attachments, newAttachment],
        },
      }));
      
      console.log(r, "RESPONSE FROM BACKEND");
    } catch (e) {
      console.log(e, "ERROR DURING FILE UPLOAD");
    }

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
