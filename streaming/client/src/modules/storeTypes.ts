import { TAttachment, TConversation } from "../types";
import { Message, TModel, TAgent } from "../types/agents";
import { TUserData, TReactionTemplate } from "../types/chatTypes";

type SetOpenedProps = {
  action: "add" | "remove";
  name: "documents" | "tags" | "completions" | "settings" | "audio";
};

type TTheme = "light" | "dark" | "system";

export type TUserPreferences = {
  theme: TTheme;
  max_memory_messages: number;
  autoplay: boolean;
  autoscroll: boolean;
  background_image_source: string;
  multiagentic_modality: "isolated" | "grupal";
  background_image_opacity: number;
};

export type TMermaidTheme = "dark" | "forest" | "neutral" | "base" | "light";

export type TPlugin = {
  name: string;
  slug: string;
  instructions: string;
  descriptionTranslationKey: string;
};

export type Store = {
  socket: any;
  messages: Message[];
  // input: string;
  theme: TTheme;
  theming: {
    mermaid: TMermaidTheme;
  };
  models: TModel[];
  agents: TAgent[];
  user?: TUserData;
  modelsAndAgents: TAgent[];
  chatState: {
    isSidebarOpened: boolean;
    attachments: TAttachment[];
    webSearch: boolean;
    writtingMode: boolean;
    useRag: boolean;
    selectedAgents: string[];
    selectedPlugins: TPlugin[];
  };
  conversation: TConversation | undefined;
  openedModals: string[];
  reactionTemplates: TReactionTemplate[];
  userPreferences: TUserPreferences;
  userTags: string[];
  setTheming: (theming: Partial<Store["theming"]>) => void;
  setPreferences: (prefs: Partial<TUserPreferences>) => void;
  setTheme: (theme: TTheme) => void;
  startup: () => void;
  removeAgent: (slug: string) => void;
  updateSingleAgent: (agent: TAgent) => void;
  setOpenedModals: (opts: SetOpenedProps) => void;
  setMessages: (messages: Message[]) => void;
  setConversation: (conversationId: string | null) => void;
  addAttachment: (newAttachment: TAttachment, saved?: boolean) => void;
  updateAttachment: (
    index: number,
    newAttachment: Partial<TAttachment>
  ) => void;
  // setInput: (input: string) => void;
  setModels: (models: TModel[]) => void;
  fetchAgents: () => void;
  toggleSidebar: () => void;
  cleanAttachments: () => void;
  deleteAttachment: (index: number) => void;
  toggleWebSearch: () => void;
  toggleWrittingMode: () => void;
  logout: () => void;
  toggleUseRag: () => void;
  toggleAgentSelected: (slug: string) => void;
  setUser: (user: TUserData) => void;
  addAgent: () => void;
  togglePlugin: (plugin: TPlugin) => void;
  updateChatState: (state: Partial<Store["chatState"]>) => void;
  test: () => void;
};
