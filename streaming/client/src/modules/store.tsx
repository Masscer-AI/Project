import { createWithEqualityFn as create } from "zustand/traditional";
import { TReactionTemplate } from "../types/chatTypes";
import {
  createRandomAgent,
  deleteAgent,
  getAgents,
  getConversation,
  getReactionTemplates,
  getTeamFeatureFlags,
  getUserPreferences,
  initConversation,
  updateUserPreferences,
  uploadDocument,
} from "./apiCalls";
import {
  isFeatureFlagsClientCacheStale,
} from "./featureFlagsConstants";
import { SocketManager } from "./socketManager";
import { STREAMING_BACKEND_URL } from "./constants";
import { TAgent } from "../types/agents";
import type { TConversation, TAgentTaskEvent } from "../types";
import toast from "react-hot-toast";
import { Store } from "./storeTypes";
import { sortAgentsBySelectionOrder } from "./agentSelection";
import {
  DEFAULT_NOTIFICATION_SETTINGS,
  syncNotificationSoundSettings,
} from "../utils/notificationSound";

const _initialTheme = (() => {
  try {
    return localStorage.getItem("cached_theme") || "dark";
  } catch {
    return "dark";
  }
})();

/** Dedupe concurrent team feature-flag fetches across components. */
let featureFlagsFetchInFlight: Promise<void> | null = null;

/** Latest async `setConversation` call wins; prevents stale GETs overwriting the UI after fast navigation. */
let conversationLoadSeq = 0;

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
  tenantBranding: null,
  agents: [],
  userPreferences: {
    theme: _initialTheme as "dark" | "light" | "system",
    max_memory_messages: 20,
    autoscroll: false,
    background_image_source: "",
    multiagentic_modality: "isolated",
    background_image_opacity: 0.5,
    notification_settings: { ...DEFAULT_NOTIFICATION_SETTINGS },
  },
  organizations: [],
  agentTaskStatus: null,
  agentTaskEvents: [],
  chatState: {
    isSidebarOpened: false,
    attachments: [],
    webSearch: false,
    writtingMode: false,
    useRag: false,
    generateImages: false,
    generateSpeech: false,
    generateVideo: false,
    createCompletions: false,

    selectedAgents: [],
    specifiedUrls: [],
  },
  conversation: undefined,
  openedModals: [],
  reactionTemplates: [],
  featureFlags: null,
  featureFlagsCheckedAt: null,
  featureFlagsLoading: false,
  featureFlagsError: null,

  invalidateFeatureFlags: () => {
    featureFlagsFetchInFlight = null;
    set({
      featureFlags: null,
      featureFlagsCheckedAt: null,
      featureFlagsLoading: false,
      featureFlagsError: null,
    });
  },

  ensureFeatureFlags: async (opts) => {
    const force = opts?.force ?? false;
    const state = get();
    if (!state.user) {
      return;
    }
    const { featureFlags, featureFlagsCheckedAt } = state;
    if (
      !force &&
      featureFlags != null &&
      featureFlagsCheckedAt != null &&
      !isFeatureFlagsClientCacheStale(featureFlagsCheckedAt)
    ) {
      return;
    }
    if (featureFlagsFetchInFlight) {
      return featureFlagsFetchInFlight;
    }
    const showLoading = state.featureFlags == null;
    if (showLoading) {
      set({ featureFlagsLoading: true, featureFlagsError: null });
    }
    featureFlagsFetchInFlight = (async () => {
      try {
        set({ featureFlagsError: null });
        const res = await getTeamFeatureFlags();
        set({
          featureFlags: res.feature_flags,
          featureFlagsCheckedAt: Date.now(),
          featureFlagsLoading: false,
          featureFlagsError: null,
        });
      } catch (err) {
        set((s) => ({
          featureFlagsLoading: false,
          featureFlagsError:
            err instanceof Error ? err : new Error(String(err)),
          // Keep prior featureFlags on background refresh failure
          featureFlags: showLoading ? null : s.featureFlags,
          featureFlagsCheckedAt: showLoading ? null : s.featureFlagsCheckedAt,
        }));
      } finally {
        featureFlagsFetchInFlight = null;
      }
    })();
    return featureFlagsFetchInFlight;
  },

  startup: async () => {
    const { fetchAgents } = get();
    const reactionTemplates: TReactionTemplate[] = await getReactionTemplates();
    set({ reactionTemplates });
    fetchAgents();
    const pref = await getUserPreferences();
    // const bodySize = new TextEncoder().encode(JSON.stringify(pref)).length;

    const notification_settings = {
      ...DEFAULT_NOTIFICATION_SETTINGS,
      ...(pref.notification_settings ?? {}),
    };
    const normalizedPref = { ...pref, notification_settings };
    syncNotificationSoundSettings(notification_settings);
    set({ userPreferences: normalizedPref });
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
    const seq = ++conversationLoadSeq;
    let data: TConversation;

    if (!conversationId) {
      data = await initConversation({ isPublic: false });
    } else {
      data = await getConversation(conversationId);
    }

    if (seq !== conversationLoadSeq) {
      return;
    }

    set(() => ({
      conversation: data,
    }));
    get().applyAgentSelectionFromConversation();
  },

  hydrateConversation: (conversation: TConversation) => {
    conversationLoadSeq += 1;
    set({ conversation });
    get().applyAgentSelectionFromConversation();
  },
  setMessages: (messages) => set({ messages }),
  setModels: (models) => set({ models }),
  addAttachment: async (newAttachment, saved = false) => {
    const { chatState } = get();
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

    const selectedAgents = chatState.selectedAgents.join(",");
    if (chatState.selectedAgents.length === 0) {
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
  applyAgentSelectionFromConversation: () => {
    const { conversation, agents } = get();
    if (!agents.length) {
      return;
    }
    if (!conversation?.id) {
      return;
    }
    if (conversation.chat_widget_id != null) {
      set((state) => ({
        agents: sortAgentsBySelectionOrder(state.agents, []),
        chatState: { ...state.chatState, selectedAgents: [] },
      }));
      return;
    }
    const related = conversation.metadata?.related_agents ?? [];
    const slugById = new Map<number, string>();
    for (const a of agents) {
      if (a.id != null) slugById.set(Number(a.id), a.slug);
    }
    const selectedSlugs: string[] = [];
    for (const ref of related) {
      const slug = slugById.get(ref.id);
      if (slug) selectedSlugs.push(slug);
    }
    set((state) => ({
      agents: sortAgentsBySelectionOrder(state.agents, selectedSlugs),
      chatState: { ...state.chatState, selectedAgents: selectedSlugs },
    }));
  },
  fetchAgents: async () => {
    const { agents, models } = await getAgents();

    const agentsCopy = agents.map((a) => ({ ...a }));

    set({
      agents: agentsCopy,
      models,
      chatState: {
        ...get().chatState,
        selectedAgents: [],
      },
    });
    get().applyAgentSelectionFromConversation();
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
    set((state) => {
      const { selectedAgents } = state.chatState;
      const newSelectedAgents = selectedAgents.includes(slug)
        ? selectedAgents.filter((s) => s !== slug)
        : [...selectedAgents, slug];
      return {
        agents: sortAgentsBySelectionOrder(state.agents, newSelectedAgents),
        chatState: {
          ...state.chatState,
          selectedAgents: newSelectedAgents,
        },
      };
    });
  },

  /** Replaces chat agent selection (slug order). Used for single-agent mode and hydration from conversation metadata. */
  setChatSelectedAgentSlugs: (slugs: string[]) => {
    set((state) => ({
      agents: sortAgentsBySelectionOrder(state.agents, slugs),
      chatState: {
        ...state.chatState,
        selectedAgents: slugs,
      },
    }));
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
  toggleGenerateSpeech: () => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        generateSpeech: !state.chatState.generateSpeech,
      },
    }));
  },
  toggleGenerateVideo: () => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        generateVideo: !state.chatState.generateVideo,
      },
    }));
  },
  toggleCreateCompletions: () => {
    set((state) => ({
      chatState: {
        ...state.chatState,
        createCompletions: !state.chatState.createCompletions,
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

  setTenantBranding: (branding) => {
    set({ tenantBranding: branding });
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
    deleteAgent(slug);
    set((state) => ({
      agents: state.agents.filter((a) => a.slug !== slug),
      chatState: {
        ...state.chatState,
        selectedAgents: state.chatState.selectedAgents.filter((s) => s !== slug),
      },
    }));
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
    if (prefs.notification_settings) {
      newPref.notification_settings = {
        ...get().userPreferences.notification_settings,
        ...prefs.notification_settings,
      };
    }
    syncNotificationSoundSettings(newPref.notification_settings);
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
    featureFlagsFetchInFlight = null;
    set({
      user: undefined,
      featureFlags: null,
      featureFlagsCheckedAt: null,
      featureFlagsLoading: false,
      featureFlagsError: null,
    });
    localStorage.removeItem("token");
    window.location.href = "/";
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

  pushAgentTaskEvent: (event: TAgentTaskEvent) => {
    set((state) => ({ agentTaskEvents: [...state.agentTaskEvents, event] }));
  },

  clearAgentTaskEvents: () => {
    set({ agentTaskEvents: [] });
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
