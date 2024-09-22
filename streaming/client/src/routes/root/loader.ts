import { LoaderFunction } from "react-router-dom";
import { initConversation } from "../../modules/apiCalls";
import { TConversationData } from "../../types/chatTypes";

export const rootLoader: LoaderFunction = async (): Promise<
  { conversation: TConversationData } | Response
> => {
  let c: TConversationData;
  try {
    // if (params.conversationId) {
    //   c = await getConversation(params.conversationId);
    // } else {
    // }
    c = await initConversation({ isPublic: true });

    return { conversation: c };
  } catch (error) {
    console.error("Error loading conversation:", error);
    // @ts-expect-error
    return {} as TConversationData;
    // return redirect("/signup");
  }
};
