import { TAttachment } from "../types";
import { Message, Model, TAgent } from "../types/agents";
import {
  TUserData,
  TConversationData,
  TReactionTemplate,
} from "../types/chatTypes";
import { AudioPlayerOptions } from "./utils";

type SetOpenedProps = {
  action: "add" | "remove";
  name: "documents" | "tags" | "completions" | "settings";
};

type TTheme = "light" | "dark" | "system";

export type TUserPreferences = {
  theme: TTheme;
  max_memory_messages: number;
  autoplay: boolean;
  autoscroll: boolean;
  background_image_source: string;
};

export type Store = {
  socket: any;
  messages: Message[];
  input: string;
  theme: TTheme;
  models: Model[];
  agents: TAgent[];
  user?: TUserData;
  modelsAndAgents: TAgent[];
  chatState: {
    isSidebarOpened: boolean;
    attachments: TAttachment[];
    webSearch: boolean;
    writtingMode: boolean;
    useRag: boolean;
    // maxMemoryMessages: number;
    // autoPlay: boolean;
    // autoScroll: boolean;
  };
  conversation: TConversationData | undefined;
  openedModals: string[];
  reactionTemplates: TReactionTemplate[];
  userPreferences: TUserPreferences;
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
  setInput: (input: string) => void;
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
  updateChatState: (state: Partial<Store["chatState"]>) => void;
  test: () => void;
};
