import { TAttachment } from "../types";

export type TConversationData = {
  title: ReactNode;
  id: string;
  messages: TMessage[];
};

export type TUserData = {
  username: string;
};

export type TChatLoader = {
  conversation: TConversationData;
  user: TUserData;
};

export type TMessage = {
  type: string;
  text: string;
  attachments: TAttachment[];
  agentSlug?: string;
};
