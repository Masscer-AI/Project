import { TAttachment, TVersion } from "../types";

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
  id?: number;
  type: string;
  text: string;
  attachments: TAttachment[];
  agent_slug?: string;
  versions?: TVersion[];
};

export type TReactionTemplate = {
  id: number;
  type: string;
  name: string;
  emoji: string;
  render_type?: string;
};
