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

export type TOrganization = {
  id: number;
  name: string;
  description: string;
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
