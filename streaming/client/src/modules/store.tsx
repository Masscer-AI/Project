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
import { Store } from "./storeTypes";

export const useStore = create<Store>()((set, get) => ({
  socket: new SocketManager(STREAMING_BACKEND_URL),
  messages: [],
  modelsAndAgents: [],
  input: "",
  theme: "dark",
  models: [],
  user: undefined,
  agents: [],
  userPreferences: {
    theme: "dark",
    max_memory_messages: 20,
    autoplay: false,
    autoscroll: false,
    background_image_source: "",
    multiagentic_modality: "isolated",
    background_image_opacity: 0.5,
  },
  chatState: {
    isSidebarOpened: false,
    attachments: [],
    webSearch: false,
    writtingMode: false,
    useRag: false,
    selectedAgents: [],
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
    const bodySize = new TextEncoder().encode(JSON.stringify(pref)).length;

    set({ userPreferences: pref });
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
      toast.success(
        "Document uploaded successfully! Now you can chat with it using all the you selected"
      );

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
    let selectedAgentsStored = localStorage.getItem("selectedAgents");

    if (!selectedAgentsStored) {
      selectFirstAI = true;
      // @ts-ignore
      selectedAgentsStored = [];
    } else {
      selectedAgentsStored = JSON.parse(selectedAgentsStored);
    }

    const agentsCopy = agents.map((a, i) => ({
      ...a,
      selected:
        (i === 0 && selectFirstAI) || selectedAgentsStored?.includes(a.slug),
    }));
    const selectedAgents =
      selectedAgentsStored && selectedAgentsStored.length > 0
        ? selectedAgentsStored
        : agentsCopy.filter((a) => a.selected).map((a) => a.slug);
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

  setUser: (user) => {
    set({ user });
  },

  addAgent: async () => {
    // const { name, slug } = getRandomWordsAndSlug();
    // const exampleAgent: TAgent = {
    //   name,
    //   slug,
    //   selected: false,
    //   act_as: "You are a helpful assistant",
    //   default: true,
    //   salute: "Hello world",
    //   frequency_penalty: 0,
    //   is_public: false,
    //   max_tokens: 2048,
    //   model_slug: "gpt-4o-mini",
    //   presence_penalty: 0,
    //   system_prompt: `{{act_as}}
    //   The context below can be useful for your task:
    //   \`\`\`
    //   {{context}}
    //   \`\`\``,
    //   temperature: 0.7,
    //   top_p: 1.0,
    // };

    // createAgent(exampleAgent);
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
    set((state) => ({
      agents: state.agents.filter((a) => a.slug !== slug),
    }));
    deleteAgent(slug);
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
      await updateUserPreferences(newPref);
    } catch (e) {
      console.log(e, "ERROR UPDATING USER PREFERENCES");
    }
  },
  logout: () => {
    set({ user: undefined });
    localStorage.removeItem("token");
    localStorage.removeItem("selectedAgents");
    window.location.href = "/";
  },

  test: () => {
    const { socket, chatState } = get();
    toast.success("Loading...");

    toast.success(chatState.selectedAgents.join(", "));

    // socket.emit("test_event", {
    //   query:
    //     examplesQueries[Math.floor(Math.random() * examplesQueries.length)],
    // });

    // socket.on("web-search", (data) => {
    //   console.log("WEB SEARCH", data);
    // });
  },
}));
