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

export type TAttachment = {
  id?: number;
  file: File | null;
  type: string;
  content: string;
  name: string;
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
