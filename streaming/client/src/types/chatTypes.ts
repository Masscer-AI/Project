import { TAttachment, TVersion } from "../types";
import { TAgent } from "./agents";

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
  query: string | null ;
};

export type TMessage = {
  id?: number;
  type: string;
  text: string;
  attachments: TAttachment[];
  agent_slug?: string;
  versions?: TVersion[];
  agents?: Partial<TAgent>[];
};

export type TReactionTemplate = {
  id: number;
  type: string;
  name: string;
  emoji: string;
  render_type?: string;
};
