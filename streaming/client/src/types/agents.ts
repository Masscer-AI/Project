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
  max_output_tokens?: number;
};

export type TOpenaiVoiceOptions =
  | "allow"
  | "shimmer"
  | "alloy"
  | "echo"
  | "fable"
  | "onyx"
  | "nova";

type TLLM = {
  name: string;
  provider: string;
  slug: string;
  max_output_tokens?: number;
};

export type TAgent = {
  name: string; // The name of the agent
  provider?: string; // The provider of the model, e.g., "openai"
  slug: string; // A unique identifier or slug for the agent
  selected: boolean; // Indicates if this agent is currently selected or active
  act_as?: string; // Optional description of the agent's role or behavior
  default?: boolean; // Optional flag to indicate if this is the default agent
  frequency_penalty?: number | null; // Optional penalty for frequency (if applicable)
  id?: number; // Optional identifier for the agent
  is_public?: boolean; // Optional flag to indicate if the agent is public
  max_tokens?: number | null; // Optional maximum number of tokens the agent can use
  model_provider?: string; // Optional provider of the model
  presence_penalty?: number | null;
  salute?: string;
  llm: TLLM;
  openai_voice?: TOpenaiVoiceOptions; // Use the new type for voice options
  profile_picture_url?: string;
  system_prompt: string;
  temperature: number;
  top_p?: number;
  conversation_title_prompt?: string | null;
  // voice?: TOpenaiVoiceOptions;
};
