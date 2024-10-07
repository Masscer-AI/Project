export interface ChatItem {
  text: string;
  audioSrc?: string;
  isUser: boolean;
}

export type TSomething = {
  ifYouAreBored: true;
  andYouJustWanna: "Add a type to avoid adding any";
};

export type TAttachment = {
  id?: number
  file: File | null;
  type: string;
  content: string;
  name: string;
};
