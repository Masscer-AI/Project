import { TAttachment } from "../types";

export type TConversationData = {
  id: string;
  messages: TMessage[];
};

export type TChatLoader = {
  conversation: TConversationData;
};

export type TMessage = {
  type: string;
  text: string;
  attachments: TAttachment[];
};
