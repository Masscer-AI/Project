/* eslint-disable @typescript-eslint/no-explicit-any */
import { TMessage } from "./types/chatTypes";

export interface ChatItem {
  text: string;
  audioSrc?: string;
  isUser: boolean;
  type: "user" | "assistant";
}

export type TSomething = {
  ifYouAreBored: true;
  andYouJustWanna: "Add a type to avoid adding any";
};

export type AttatchmentMode = "all_possible_text" | "similar_chunks";

export type TAttachment = {
  text?: string;
  id?: number | string;
  file?: File | null;
  type: string;
  content: string;
  name: string;
  mode?: AttatchmentMode;
};

export interface TConversation {
  id: string;
  user_id: number;
  number_of_messages: number;
  tags?: string[];
  title: undefined | string;
  created_at: string;
  messages?: TMessage[];
  summary?: string;
}

export type TCompletion = {
  id: number;
  prompt: string;
  answer: string;
  approved: boolean;
  agent: number;
};

type TWebSearchResult = {
  url: string;
  content: string;
};

export type TSource = {
  model_id: number;
  model_name: string;
  content: string;
  extra: string;
};

type TUsage = {
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
  model_slug?: string;
};

export type TVersion = {
  text: string;
  type: string;
  agent_slug: string;
  agent_name: string;
  web_search_results?: TWebSearchResult[];
  sources?: TSource[];
  usage?: TUsage;
};

export type TOrganizationCredentials = {
  openai_api_key: string;
  brave_api_key: string;
  anthropic_api_key: string;
  pexels_api_key: string;
  elevenlabs_api_key: string;
  heygen_api_key: string;
};

export type TOrganization = {
  id: string;
  name: string;
  description: string;
  credentials: TOrganizationCredentials;
};

export type TDocument = {
  text: string;
  total_tokens: number;
  id: number;
  name: string;
  brief: string;
  chunk_count: number;
  chunk_set: any[];
};

export interface TConversationAlertRule {
  id: string;
  name: string;
  trigger: string;
  extractions: Record<string, any>;
  scope: "all_conversations" | "selected_agents";
  enabled: boolean;
  notify_to: "all_staff" | "selected_members";
  organization: string;
  created_by: number | null;
  created_at: string;
  updated_at: string;
}

export interface TConversationAlert {
  id: string;
  title: string;
  reasoning: string;
  extractions: Record<string, any>;
  status: "PENDING" | "NOTIFIED" | "RESOLVED" | "DISMISSED";
  conversation: string;
  conversation_title: string;
  conversation_id: string;
  alert_rule: TConversationAlertRule;
  resolved_by: number | null;
  resolved_by_username: string | null;
  dismissed_by: number | null;
  dismissed_by_username: string | null;
  created_at: string;
  updated_at: string;
}

export interface TAlertStats {
  total: number;
  pending: number;
  notified: number;
  resolved: number;
  dismissed: number;
}
