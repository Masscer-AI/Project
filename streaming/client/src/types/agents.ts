export type Message = {
  sender: string;
  text: string;
  imageUrl?: string;
};

type TModelPricing = {
  output: string;
  prompt: string;
};

type TOutputMode = "text" | "image";

export type TModel = {
  name: string;
  provider: string;
  slug: string;
  selected: boolean;
  pricing: {
    [key in TOutputMode]: TModelPricing;
  };
};

type TLLM = {
  name: string;
  provider: string;
  slug: string;
};

export type TAgentKind = "conversational_agent" | "platform_assistant";

export type TVoiceCatalogEntry = {
  id: string;
  name: string;
  slug: string;
  provider: string;
  scope: string;
};

export type TAgent = {
  name: string;
  provider?: string;
  slug: string;
  agent_kind?: TAgentKind;
  act_as?: string;
  default?: boolean;
  id?: number;
  is_public?: boolean;
  max_tokens?: number | null;
  model_provider?: string;
  salute?: string;
  llm: TLLM;
  default_voice_id?: string | null;
  profile_picture_url?: string;
  system_prompt: string;
  conversation_title_prompt?: string;
  organization?: string | null;
  user?: number;
  access_mode?: "personal" | "org_all" | "org_roles" | "platform";
  allowed_roles?: { id: string; name: string }[];
};
