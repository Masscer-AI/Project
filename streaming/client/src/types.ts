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
  text: any;
  id?: number;
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
  title: undefined | string;
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

export type TVersion = {
  text: string;
  type: string;
  agent_slug: string;
  web_search_results?: TWebSearchResult[];
};
