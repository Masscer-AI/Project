import { TAttachment, TConversation, TVersion } from "../types";
import { TAgent } from "./agents";



export type TUserProfile = {
  avatar_url: string;
  bio: string;
  sex: string;
  age: number;
  birthday: string;
  name: string;
};

export type TUserData = {
  username: string;
  email: string;
  profile?: TUserProfile;
};

export type TChatLoader = {
  conversation: TConversation;
  user: TUserData;
  query: string | null;
  sendQuery: boolean;
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
