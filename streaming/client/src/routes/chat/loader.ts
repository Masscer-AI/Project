import { LoaderFunction, redirect } from "react-router-dom";
import { initConversation, getConversation } from "../../modules/apiCalls";
import { TConversationData } from "../../types/chatTypes";

export const chatLoader: LoaderFunction = async ({
  request,
}): Promise<{ conversation: TConversationData } | Response> => {
  let c: TConversationData;
  try {
    console.log("Loading page!");
    const url = new URL(request.url);
    const conversationId = url.searchParams.get("conversation");
    if (conversationId) {
      c = await getConversation(conversationId);
    } else {
      c = await initConversation({ isPublic: false });
    }

    return { conversation: c };
  } catch (error) {
    console.error("Error loading conversation:", error);
    return redirect("/signup");
  }
};
