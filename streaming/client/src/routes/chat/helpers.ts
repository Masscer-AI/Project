import toast from "react-hot-toast";
import { TMessage } from "../../types/chatTypes";

export const addAssistantMessageChunk = (
  chunk: string,
  agentSlug: string,
  prevMessages: TMessage[],
  multiagenticModality: "isolated" | "grupal"
) => {
  const newMessages = [...prevMessages];
  const lastMessage = newMessages[newMessages.length - 1];

  if (lastMessage && lastMessage.type === "assistant") {
    const lastAgent = lastMessage.agent_slug;

    if (lastAgent === agentSlug) {
      lastMessage.text += chunk;
    }

    if (lastAgent !== agentSlug && multiagenticModality === "grupal") {
      const assistantMessage: TMessage = {
        type: "assistant",
        text: chunk,
        attachments: [],
        agent_slug: agentSlug,
        versions: [
          {
            text: chunk,
            type: "assistant",
            agent_slug: agentSlug,
            agent_name: agentSlug,
          },
        ],
      };
      newMessages.push(assistantMessage);
      return newMessages;
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
    console.log("New message appended to conversation");

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

export const updateLastMessagesIds = (data, prevMessages, nextAgentSlug) => {
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

  if (nextAgentSlug) {

    const assistantMessage: TMessage = {
      type: "assistant",
      text: "",
      attachments: [],
      agent_slug: nextAgentSlug,
      versions: [
        {
          text: "",
          type: "assistant",
          agent_slug: nextAgentSlug,
          agent_name: nextAgentSlug,
        },
      ],
    };
    newMessages.push(assistantMessage);
  } 
  return newMessages;
};
