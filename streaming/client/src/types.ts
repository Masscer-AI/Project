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
  /** When type is "completion", links to a finetuning Completion row. */
  completion_id?: number;
  approved?: boolean;
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

export type TConversationActiveTakeover = {
  id: string;
  operator_user_id: number;
  operator_username: string;
  operator_display_name: string;
  status: "ACTIVE" | "INACTIVE";
  started_at: string | null;
};

export interface TConversation {
  id: string;
  user_id?: number | null;
  user_username?: string | null;
  chat_widget_id?: number | null;
  ws_number?: number | null;
  whatsapp_user_number?: string | null;
  active_takeover?: TConversationActiveTakeover | null;
  is_anonymous_widget?: boolean;
  visitor_alias?: string | null;
  status?: "active" | "inactive" | "archived" | "deleted";
  last_message_at?: string | null;
  archived_at?: string | null;
  deleted_at?: string | null;
  number_of_messages: number;
  tags?: number[];
  title: undefined | string;
  created_at: string;
  messages?: TMessage[];
  summary?: string;
  metadata?: {
    related_agents?: { id: number }[];
  };
  alerts_count?: number;
  alert_rule_ids?: string[];
  has_pending_alerts?: boolean;
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

export type TAgentSessionToolCall = {
  order: number;
  iteration: number | null;
  call_id: string;
  tool_name: string;
  arguments: unknown;
  result: unknown;
  result_preview: string;
  error: string | null;
};

export type TAgentSessionExecutionLog = {
  session_id: string;
  agent_index: number;
  agent_slug: string | null;
  model_slug: string | null;
  iterations: number;
  tool_calls_count: number;
  total_duration: number | null;
  started_at: string;
  ended_at: string | null;
  status: string;
  tool_calls: TAgentSessionToolCall[];
};

export type TAgentSessionExecutionLogResponse = {
  sessions: TAgentSessionExecutionLog[];
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
  anthropic_api_key: string;
  pexels_api_key: string;
  elevenlabs_api_key: string;
  heygen_api_key: string;
};

export type TOrganization = {
  id: string;
  name: string;
  description: string;
  /** Organization owner's Django user id (serialized FK). */
  owner?: number;
  credentials: TOrganizationCredentials;
  can_manage?: boolean;
  is_owner?: boolean;
  logo_url?: string | null;
};

/** Word (.docx) template with Jinja-style placeholders for org agents */
export type TDocumentTemplateVariable = {
  description: string;
  required: boolean;
  example: string;
};

export type TDocumentTemplate = {
  id: string;
  organization_id: string;
  name: string;
  description: string;
  is_active: boolean;
  original_filename: string;
  file_size: number;
  content_type: string;
  metadata: {
    placeholders?: string[];
    variables?: Record<string, TDocumentTemplateVariable>;
  };
  file_url: string;
  created_at: string | null;
  updated_at: string | null;
};

export type TAgentTemplateAssignment = {
  id: string;
  agent_id: number;
  agent_slug: string;
  template_id: string;
  template_name: string;
  usage_instructions: string;
  is_enabled: boolean;
  created_at: string | null;
  updated_at: string | null;
};

export type TSubscriptionPlan = {
  slug: string;
  display_name: string;
  monthly_price_usd: string;
  credits_limit_usd: string | null;
  duration_days: number | null;
};

export type TOrganizationSubscription = {
  id: string;
  status: "trial" | "active" | "expired" | "cancelled" | "pending_payment";
  payment_method: "stripe" | "manual";
  is_active: boolean;
  start_date: string | null;
  end_date: string | null;
  display_monthly_price_usd?: string;
  contract_price_usd?: string | null;
  billing_interval?: "monthly" | "quarterly" | "yearly" | "one_time" | "custom";
  cancel_at_period_end?: boolean;
  cancel_at?: string | null;
  stripe_status?: string | null;
  plan: TSubscriptionPlan;
};

export type TOrganizationWallet = {
  subscription_balance: string;
  purchased_balance: string;
  /** Total compute units (subscription + purchased) */
  balance: string;
  unit_name: string;
  one_usd_is: number;
  subscription_balance_usd: string;
  purchased_balance_usd: string;
  balance_usd: string;
};

export type TOrganizationBilling = {
  subscription: TOrganizationSubscription | null;
  wallet: TOrganizationWallet | null;
};

export type TOrganizationMember = {
  id: number;
  email: string;
  username: string;
  profile_name: string;
  bio: string;
  is_owner: boolean;
  is_active: boolean;
  expires_at: string | null;
  current_role?: { id: string; name: string; assignment_id?: string } | null;
};

export type TOrganizationInvite = {
  id: string;
  email: string;
  name: string;
  bio: string;
  expires_at: string | null;
  status: string;
  invite_expires_at: string;
  created_at: string;
  accepted_at: string | null;
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
  content_type?: string;
  has_file?: boolean;
  file_url?: string | null;
  created_at?: string;
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
  /** Agents this rule applies to when scope is `selected_agents`. */
  agent_ids?: number[];
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

export interface TNotificationCondition {
  subject: "n_alerts";
  condition: string;
  delivery_method: "app" | "email" | "all";
  message: string;
}

export type TNotifyToType = "user" | "role" | "organization";

/** In-app notification row (notify.UserNotification). */
export interface TUserNotification {
  id: string;
  organization: string;
  notification_rule: string;
  alert: string;
  message: string;
  delivery_method: "app" | "email" | "all";
  delivered_at: string | null;
  read_at: string | null;
  ignored_at: string | null;
  expires_at: string | null;
  created_at: string;
}

/** Response from POST /v1/notify/notification-rules/build/ (LLM draft, not persisted). */
export interface TNotificationRuleBuildResponse {
  alert_rule_id: string;
  alert_rule_name: string | null;
  conditions: TNotificationCondition[];
  assistant_summary: string;
}

export interface TNotificationRule {
  id: string;
  organization: string;
  alert_rule_id: string;
  alert_rule_name: string | null;
  notify_to_user_id: number | null;
  notify_to_user_username: string | null;
  notify_to_role_id: string | null;
  notify_to_role_name: string | null;
  notify_to_org_id: string | null;
  notify_to_org_name: string | null;
  conditions: TNotificationCondition[];
  enabled: boolean;
  created_by: number | null;
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
  avatar_image: string;
  first_message: string;
  capabilities: TWidgetCapability[];
  style: {
    primary_color?: string;
    theme?: "default" | "light" | "dark";
    show_history?: boolean;
    allow_visitor_attachments?: boolean;
  };
  agent_slug: string | null;
  agent_name: string | null;
  embed_code: string;
  created_at: string;
  updated_at: string;
}

export type TWidgetCapabilityType = "internal_tool";

export interface TWidgetCapability {
  name: string;
  type: TWidgetCapabilityType;
  enabled: boolean;
}
