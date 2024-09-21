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
    imageUrl?: string;
  };