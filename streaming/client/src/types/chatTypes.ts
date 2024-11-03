import { TAttachment } from "../types";

export type TConversationData = {
  title: string;
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
  agent_slug?: string;
  versions?: {
    text: string;
    type: string;
    agent_slug: string;
  }[];
};

export type TReactionTemplate = {
  id: number;
  type: string;
  name: string;
  emoji: string;
  render_type?: string;
};
