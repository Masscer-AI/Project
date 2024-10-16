import { createWithEqualityFn as create } from "zustand/traditional";
import { TConversationData, TUserData } from "../types/chatTypes";
import {
  createAgent,
  getAgents,
  getConversation,
  initConversation,
  uploadDocument,
} from "./apiCalls";
import { TAttachment } from "../types";
import { SocketManager } from "./socketManager";
import { getRandomWordsAndSlug, STREAMING_BACKEND_URL } from "./constants";
import { Agent, Message, Model } from "../types/agents";
import toast from "react-hot-toast";

type SetOpenedProps = {
  action: "add" | "remove";
  name: "documents" | "tags" | "completions";
};

type Store = {
  socket: any;
  messages: Message[];
  input: string;
  model: Model;
  models: Model[];
  agents: Agent[];
  user?: TUserData;
  modelsAndAgents: Agent[];
  chatState: {
    isSidebarOpened: boolean;
    attachments: TAttachment[];
    webSearch: boolean;
    writtingMode: boolean;
    useRag: boolean;
  };
  conversation: TConversationData | undefined;
  openedModals: string[];
  setOpenedModals: (opts: SetOpenedProps) => void;
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
  toggleWebSearch: () => void;
  toggleWrittingMode: () => void;
  toggleUseRag: () => void;
  toggleAgentSelected: (slug: string) => void;
  setUser: (user: TUserData) => void;
  addAgent: () => void;
};

export const useStore = create<Store>()((set, get) => ({
  socket: new SocketManager(STREAMING_BACKEND_URL),
  messages: [],
  modelsAndAgents: [],
  input: "",
  model: { name: "gpt-4o", provider: "openai", slug: "gpt-4o", selected: true },
  models: [
    { name: "gpt-4o", provider: "openai", slug: "gpt-4o", selected: true },
    // { name: "gpt-4o-mini", provider: "openai" },
    // { name: "claude-3-5-sonnet-20240620", provider: "anthropic" },
  ],
  user: undefined,
  agents: [],
  chatState: {
    isSidebarOpened: false,
    attachments: [],
    webSearch: false,
    writtingMode: false,
    useRag: false,
  },
  conversation: undefined,
  openedModals: [],

  setOpenedModals: ({ action, name }) => {
    const { openedModals } = get();
    const copy = [...openedModals];
    const index = copy.indexOf(name);

    if (action === "add" && index === -1) {
      copy.push(name);
    } else if (action === "remove" && index !== -1) {
      copy.splice(index, 1);
    }

    set({ openedModals: copy });
  },
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
    const { agents } = get();
    const formData = new FormData();

    if (newAttachment.type.includes("image")) {
      set((state) => ({
        chatState: {
          ...state.chatState,
          attachments: [...state.chatState.attachments, newAttachment],
        },
      }));
      return;
    }

    const selectedAgents = agents.map((a) => a.slug);
    if (selectedAgents.length === 0) {
      toast.error("No agents selected, please select one to attach the ");
    } else {
      console.log("SELECTED AGENTS");
      console.log(selectedAgents);
    }
    // TODO: Make this possible, persist information
    // toast.error("NOT IMPLEMENTED ERROR IN STORE LINE 133");
    // formData.append("agent_slug", chatState.selectedAgent);
    formData.append("name", newAttachment.name);
    formData.append("conversation_id", String(conversation_id));

    // @ts-ignore
    formData.append("file", newAttachment.file);
    try {
      const r = await uploadDocument(formData);
      newAttachment.id = r.id;
      console.log("ADDED ATTACHMENT IN DB", r);

      set((state) => ({
        chatState: {
          ...state.chatState,
          attachments: [...state.chatState.attachments, newAttachment],
        },
      }));
    } catch (e) {
      console.log(e, "ERROR DURING FILE UPLOAD");
    }
  },
  fetchAgents: async () => {
    const { agents, models } = await getAgents();

    // console.log(agents, "AGENTS FROM DB");

    const agentsCopy = agents.map((a, i) => ({
      ...a,
      selected: i === 0,
    }));
    set({
      agents: agentsCopy,
      models,
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
  toggleAgentSelected: (slug: string) => {
    const { agents } = get();

    const copy = agents.map((a) => {
      if (a.slug == slug) {
        return {
          ...a,
          selected: !a.selected,
        };
      } else {
        return a;
      }
    });

    set({ agents: copy });
  },
  toggleWebSearch: () => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        webSearch: !state.chatState.webSearch,
      },
    }));
  },
  toggleWrittingMode: () => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        writtingMode: !state.chatState.writtingMode,
      },
    }));
  },
  toggleUseRag: () => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        useRag: !state.chatState.useRag,
      },
    }));
  },

  setUser: (user) => {
    set({ user });
  },

  addAgent: () => {
    const { name, slug } = getRandomWordsAndSlug();
    const exampleAgent: Agent = {
      name,
      slug,
      selected: false,
      act_as: "You are a helpful assistant",
      default: true,
      salute: "Hello world",
      frequency_penalty: 0.5,
      is_public: false,
      max_tokens: 2048,
      model_slug: "gpt-4o-mini",
      presence_penalty: 0.3,
      system_prompt: `{{act_as}}
      The following context may be useful for your task:
      \`\`\`
      {{context}}
      \`\`\``,
      temperature: 0.7,
      top_p: 0.9,
    };

    set((state) => ({
      agents: [...state.agents, exampleAgent],
    }));

    createAgent(exampleAgent);
  },
}));
