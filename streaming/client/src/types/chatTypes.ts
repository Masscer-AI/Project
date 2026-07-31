import { TAttachment, TConversation, TVersion } from "../types";
import { TAgent } from "./agents";

export type TPhoneNumber = {
  country_code: string;
  number: string;
  is_default: boolean;
};

export type TUserProfile = {
  id: string;
  avatar_url: string;
  bio: string;
  sex: string;
  age: number;
  birthday: string;
  name: string;
  phone_numbers?: TPhoneNumber[];
};

export type TUserData = {
  id?: number;
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

export type TMessageMetadata = {
  source?: string;
  scheduled_task_id?: string;
  scheduled_task_title?: string;
  scheduled_task_kind?: string;
  schedule_type?: string;
  [key: string]: unknown;
};

export type TMessage = {
  id?: number;
  type: string;
  text: string;
  attachments: TAttachment[];
  agent_slug?: string;
  versions?: TVersion[];
  agents?: Partial<TAgent>[];
  index?: number;
  metadata?: TMessageMetadata;
};

export type TReactionTemplate = {
  id: number;
  type: string;
  name: string;
  emoji: string;
  render_type?: string;
};
