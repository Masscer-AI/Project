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
  attachment_id?: string;
  file?: File | null;
  type: string;
  content: string;
  name: string;
  mode?: AttatchmentMode;
};

export interface TTag {
  id: number;
  title: string;
  description: string;
  color?: string;
  enabled: boolean;
  organization: string;
  created_at: string;
  updated_at: string;
}

export interface TConversation {
  id: string;
  user_id?: number | null;
  user_username?: string | null;
  number_of_messages: number;
  tags?: number[];
  title: undefined | string;
  created_at: string;
  messages?: TMessage[];
  summary?: string;
  alerts_count?: number;
  alert_rule_ids?: string[];
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

export type TAgentSession = {
  id: string;
  task_type: string;
  iterations: number;
  tool_calls_count: number;
  total_duration: number | null;
  agent_index: number;
  agent_slug: string | null;
  model_slug: string | null;
  started_at: string;
  ended_at: string | null;
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
  can_manage?: boolean;
  is_owner?: boolean;
  logo_url?: string | null;
};

export type TOrganizationMember = {
  id: number;
  email: string;
  username: string;
  profile_name: string;
  is_owner: boolean;
  is_active: boolean;
  current_role?: { id: string; name: string; assignment_id?: string } | null;
};

export type TOrganizationRole = {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  capabilities: string[];
  created_at: string;
  updated_at: string;
};

export type TRoleAssignment = {
  id: string;
  user: number;
  user_id?: number;
  organization: string;
  role: string;
  role_name: string;
  from_date: string;
  to_date: string | null;
  created_at: string;
  updated_at: string;
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

export type TWebPage = {
  id: number;
  url: string;
  title?: string;
  is_pinned: boolean;
  created_at: string;
  updated_at: string;
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

export interface TChatWidget {
  id: number;
  token: string;
  name: string;
  enabled: boolean;
  web_search_enabled: boolean;
  rag_enabled: boolean;
  plugins_enabled: string[];
  agent_slug: string | null;
  agent_name: string | null;
  embed_code: string;
  created_at: string;
  updated_at: string;
}
