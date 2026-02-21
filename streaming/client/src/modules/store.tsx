import { createWithEqualityFn as create } from "zustand/traditional";
import { TReactionTemplate } from "../types/chatTypes";
import {
  createRandomAgent,
  deleteAgent,
  getAgents,
  getConversation,
  getReactionTemplates,
  getUserPreferences,
  initConversation,
  updateUserPreferences,
  uploadDocument,
} from "./apiCalls";
import { SocketManager } from "./socketManager";
import { STREAMING_BACKEND_URL } from "./constants";
import { TAgent } from "../types/agents";
import toast from "react-hot-toast";
import { Store, TPlugin } from "./storeTypes";

const _initialTheme = (() => {
  try {
    return localStorage.getItem("cached_theme") || "dark";
  } catch {
    return "dark";
  }
})();


export const useStore = create<Store>()((set, get) => ({
  socket: new SocketManager(STREAMING_BACKEND_URL),
  messages: [],
  modelsAndAgents: [],
  theme: _initialTheme as "dark" | "light" | "system",
  theming: {
    mermaid: "dark",
  },
  models: [],
  user: undefined,
  agents: [],
  userPreferences: {
    theme: _initialTheme as "dark" | "light" | "system",
    max_memory_messages: 20,
    autoplay: false,
    autoscroll: false,
    background_image_source: "",
    multiagentic_modality: "isolated",
    background_image_opacity: 0.5,
  },
  organizations: [],
  agentTaskStatus: null,
  chatState: {
    isSidebarOpened: false,
    attachments: [],
    webSearch: false,
    writtingMode: false,
    useRag: false,
    generateImages: false,
    useAgentTask: undefined,

    selectedAgents: [],
    selectedPlugins: [],
    specifiedUrls: [],
  },
  conversation: undefined,
  openedModals: [],
  reactionTemplates: [],
  startup: async () => {
    const { fetchAgents } = get();
    const reactionTemplates: TReactionTemplate[] = await getReactionTemplates();
    set({ reactionTemplates });
    fetchAgents();
    const pref = await getUserPreferences();
    // const bodySize = new TextEncoder().encode(JSON.stringify(pref)).length;

    set({ userPreferences: pref });
    try {
      if (pref.theme) localStorage.setItem("cached_theme", pref.theme);
    } catch {}
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
  setModels: (models) => set({ models }),
  addAttachment: async (newAttachment, saved = false) => {
    const { agents } = get();
    const formData = new FormData();

    if (newAttachment.type.includes("image")) {
      newAttachment.mode = "all_possible_text";

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

    if (saved) {
      set((state) => ({
        chatState: {
          ...state.chatState,
          attachments: [...state.chatState.attachments, newAttachment],
        },
      }));
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
    // formData.append("agents", selectedAgents);
    formData.append("name", newAttachment.name);
    // formData.append("conversation_id", String(conversation_id));

    const loadingID = toast.loading("Uploading document...");
    // @ts-ignore
    formData.append("file", newAttachment.file);
    try {
      const r = await uploadDocument(formData);
      console.log(r, "RESPONSE FROM UPLOADING DOCUMENT");

      newAttachment.id = r.id;
      newAttachment.text = r.text;
      toast.dismiss(loadingID);

      newAttachment.mode = "all_possible_text";

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
  updateAttachment: (index, newAttachment) => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        attachments: state.chatState.attachments.map((a, i) =>
          i === index ? { ...a, ...newAttachment } : a
        ),
      },
    }));
  },
  fetchAgents: async () => {
    const { agents, models } = await getAgents();

    let selectFirstAI = false;
    const selectedAgentsStored = localStorage.getItem("selectedAgents");
    let selectedAgentsSlugs: string[] = [];

    if (!selectedAgentsStored) {
      selectFirstAI = true;
    } else {
      selectedAgentsSlugs = JSON.parse(selectedAgentsStored);
    }

    const agentsCopy = agents.map((a, i) => ({
      ...a,
      selected:
        (i === 0 && selectFirstAI) || selectedAgentsStored?.includes(a.slug),
    }));

    const selectedAgents =
      selectedAgentsStored && selectedAgentsStored.length > 0
        ? selectedAgentsSlugs.filter((a) =>
            agentsCopy.some((a2) => a2.slug === a)
          )
        : agentsCopy.filter((a) => a.selected).map((a) => a.slug);

    agentsCopy.sort((a, b) => {
      const indexA = selectedAgents.indexOf(a.slug);
      const indexB = selectedAgents.indexOf(b.slug);

      return indexA === -1 ? 1 : indexB === -1 ? -1 : indexA - indexB;
    });

    set({
      agents: agentsCopy,
      models,
      chatState: {
        ...get().chatState,
        // @ts-ignore
        selectedAgents: selectedAgents,
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
  toggleAgentSelected: (slug: string) => {
    const { agents, chatState } = get();

    const selectedAgents = chatState.selectedAgents;
    let newSelectedAgents: string[] = [];
    if (selectedAgents.includes(slug)) {
      newSelectedAgents = selectedAgents.filter((a) => a !== slug);
    } else {
      newSelectedAgents = [...selectedAgents, slug];
    }

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

    copy.sort((a, b) => {
      const indexA = newSelectedAgents.indexOf(a.slug);
      const indexB = newSelectedAgents.indexOf(b.slug);

      return indexA === -1 ? 1 : indexB === -1 ? -1 : indexA - indexB;
    });

    set({ agents: copy });
    set((state) => ({
      chatState: {
        ...state.chatState,
        selectedAgents: newSelectedAgents,
      },
    }));
    if (newSelectedAgents.length > 0) {
      localStorage.setItem("selectedAgents", JSON.stringify(newSelectedAgents));
    } else {
      localStorage.removeItem("selectedAgents");
    }
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
  toggleGenerateImages: () => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        generateImages: !state.chatState.generateImages,
      },
    }));
  },

  setUser: (user) => {
    const { socket } = get();

    if (user.id) {
      socket.emit("register_user", user.id);
    } else {
      console.log("The user has no id");
    }

    set({ user });
  },

  addAgent: async () => {
    const a = await createRandomAgent();
    set((state) => ({
      agents: [...state.agents, a],
    }));
  },
  updateSingleAgent: (agent: TAgent) => {
    set((state) => ({
      agents: state.agents.map((a) => (a.slug === agent.slug ? agent : a)),
    }));
  },
  removeAgent: (slug: string) => {
    const { chatState } = get();
    set((state) => ({
      agents: state.agents.filter((a) => a.slug !== slug),
    }));
    deleteAgent(slug);
    // Remove the agent from the selectedAgents array

    const selectedAgents = chatState.selectedAgents.filter((a) => a !== slug);

    set((state) => ({
      chatState: {
        ...state.chatState,
        selectedAgents: selectedAgents,
      },
    }));
    localStorage.setItem("selectedAgents", JSON.stringify(selectedAgents));
  },
  // This must update partial the chatState
  updateChatState: (partial) => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        ...partial,
      },
    }));
  },
  setTheme: (theme) => {
    set({ theme });
  },
  setPreferences: async (prefs) => {
    const newPref = { ...get().userPreferences, ...prefs };
    set({ userPreferences: newPref });
    try {
      if (newPref.theme) localStorage.setItem("cached_theme", newPref.theme);
    } catch {}
    try {
      await updateUserPreferences(newPref);
    } catch (e) {
      console.log(e, "ERROR UPDATING USER PREFERENCES");
    }
  },

  setTheming: (theming: Partial<Store["theming"]>) => {
    set((state) => ({
      theming: {
        ...state.theming,
        ...theming,
      },
    }));
  },
  logout: () => {
    set({ user: undefined });
    localStorage.removeItem("token");
    localStorage.removeItem("selectedAgents");
    window.location.href = "/";
  },

  togglePlugin: (plugin: TPlugin) => {
    const { chatState } = get();

    let newSelectedPlugins: TPlugin[] = [];
    if (chatState.selectedPlugins.some((p) => p.slug === plugin.slug)) {
      newSelectedPlugins = chatState.selectedPlugins.filter(
        (p) => p.slug !== plugin.slug
      );
    } else {
      newSelectedPlugins = [...chatState.selectedPlugins, plugin];
    }

    set((state) => ({
      chatState: {
        ...state.chatState,
        selectedPlugins: newSelectedPlugins,
      },
    }));
  },
  setSpecifiedUrls: (urls: Store["chatState"]["specifiedUrls"]) => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        specifiedUrls: urls,
      },
    }));
  },

  setAgentTaskStatus: (status: string | null) => {
    set({ agentTaskStatus: status });
  },

  test: () => {
    // const { chatState, agents } = get();
    // toast.success("Loading...");
    // console.log(agents, "AGENTS");
    // console.log(chatState.selectedAgents, "SELECTED AGENTS");
    // // Clean selected agents
    // set((state) => ({
    //   chatState: {
    //     ...state.chatState,
    //     selectedAgents: [],
    //   },
    // }));
    // localStorage.removeItem("selectedAgents");
    // socket.emit("test_event", {
    //   query:
    //     examplesQueries[Math.floor(Math.random() * examplesQueries.length)],
    // });
    // socket.on("web-search", (data) => {
    //   console.log("WEB SEARCH", data);
    // });
  },
}));
