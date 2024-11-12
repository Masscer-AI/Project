export type Message = {
  sender: string;
  text: string;
  imageUrl?: string;
};

export type Model = {
  name: string;
  provider: string;
  slug: string;
  selected: boolean;
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
  model_slug?: string;
  presence_penalty?: number | null;
  salute?: string;
  profile_picture_url?: string;
  system_prompt: string;
  temperature: number;
  top_p?: number;
};
