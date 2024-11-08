import { createWithEqualityFn as create } from "zustand/traditional";
import { TReactionTemplate } from "../types/chatTypes";
import {
  createAgent,
  deleteAgent,
  getAgents,
  getConversation,
  getReactionTemplates,
  initConversation,
  uploadDocument,
} from "./apiCalls";
import { SocketManager } from "./socketManager";
import { getRandomWordsAndSlug, STREAMING_BACKEND_URL } from "./constants";
import { TAgent } from "../types/agents";
import toast from "react-hot-toast";
import { Store } from "./storeTypes";

export const useStore = create<Store>()((set, get) => ({
  socket: new SocketManager(STREAMING_BACKEND_URL),
  messages: [],
  modelsAndAgents: [],
  input: "",
  model: { name: "gpt-4o", provider: "openai", slug: "gpt-4o", selected: true },
  models: [],
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
  reactionTemplates: [],
  startup: async () => {
    const { fetchAgents } = get();
    const reactionTemplates: TReactionTemplate[] = await getReactionTemplates();
    set({ reactionTemplates });
    fetchAgents();
  },
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

    if (newAttachment.type === "audio") {
      return;
      // Is an audio is passed, ask the user it it wants to use gpt-4o-audio-preview
      set((state) => ({
        chatState: {
          ...state.chatState,
          attachments: [...state.chatState.attachments, newAttachment],
        },
      }));
      toast.success("Adding audio...");
      return;
    }

    const selectedAgents = agents
      .filter((a) => a.selected)
      .map((a) => a.slug)
      .join(",");
    if (selectedAgents.length === 0) {
      toast.error(
        "No agents selected, please  at least one to attach the documents on its vector store"
      );
    }
    formData.append("agents", selectedAgents);
    formData.append("name", newAttachment.name);
    formData.append("conversation_id", String(conversation_id));

    const loadingID = toast.loading("Uploading document...");
    // @ts-ignore
    formData.append("file", newAttachment.file);
    try {
      const r = await uploadDocument(formData);
      newAttachment.id = r.id;

      toast.dismiss(loadingID);
      toast.success(
        "Document uploaded successfully! Now you can chat with it using all the you selected"
      );

      console.log("NEW ATTACHMENT", newAttachment);

      set((state) => ({
        chatState: {
          ...state.chatState,
          attachments: [...state.chatState.attachments, newAttachment],
          useRag: true,
        },
      }));
    } catch (e) {
      console.log(e, "ERROR DURING FILE UPLOAD");
      toast.dismiss(loadingID);
    }
  },
  fetchAgents: async () => {
    const { agents, models } = await getAgents();

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
    const exampleAgent: TAgent = {
      name,
      slug,
      selected: false,
      act_as: "You are a helpful assistant",
      default: true,
      salute: "Hello world",
      frequency_penalty: 0,
      is_public: false,
      max_tokens: 2048,
      model_slug: "gpt-4o-mini",
      presence_penalty: 0,
      system_prompt: `{{act_as}}
      The context below can be useful for your task:
      \`\`\`
      {{context}}
      \`\`\``,
      temperature: 0.7,
      top_p: 1.0,
    };

    set((state) => ({
      agents: [...state.agents, exampleAgent],
    }));

    createAgent(exampleAgent);
  },
  updateSingleAgent: (agent: TAgent) => {
    set((state) => ({
      agents: state.agents.map((a) => (a.slug === agent.slug ? agent : a)),
    }));
  },
  removeAgent: (slug: string) => {
    set((state) => ({
      agents: state.agents.filter((a) => a.slug !== slug),
    }));
    deleteAgent(slug);
  }
}));
