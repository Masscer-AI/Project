import { TMessage } from "../../types/chatTypes";

export const updateMessages = (
  chunk: string,
  agentSlug: string,
  prevMessages: TMessage[]
) => {
  const newMessages = [...prevMessages];
  const lastMessage = newMessages[newMessages.length - 1];

  if (lastMessage && lastMessage.type === "assistant") {
    if (lastMessage.agent_slug === agentSlug) {
      lastMessage.text += chunk;
    }
    const targetVersion = lastMessage.versions?.find(
      (v) => v.agent_slug === agentSlug
    );
    if (targetVersion) {
      targetVersion.text += chunk;
    } else {
      lastMessage.versions = [
        ...(lastMessage.versions || []),
        {
          text: chunk,
          type: "assistant",
          agent_slug: agentSlug,
          agent_name: agentSlug,
        },
      ];
    }
  } else {
    const assistantMessage: TMessage = {
      type: "assistant",
      text: chunk,
      attachments: [],
      agent_slug: agentSlug,
    };
    assistantMessage.versions = [
      {
        text: chunk,
        type: "assistant",
        agent_slug: agentSlug,
        agent_name: agentSlug,
      },
    ];
    newMessages.push(assistantMessage);
  }
  return newMessages;
};

export const updateLastMessagesIds = (data, prevMessages) => {
  const newMessages = [...prevMessages];
  newMessages.reverse();

  const lastAIMessage = newMessages.find((m) => m.type === "assistant");
  if (lastAIMessage) {
    lastAIMessage.id = data.ai_message_id;
    lastAIMessage.versions = data.versions;
  }
  const lastUserMessage = newMessages.find((m) => m.type === "user");
  if (lastUserMessage) {
    lastUserMessage.id = data.user_message_id;
  }
  newMessages.reverse();
  return newMessages;
};
