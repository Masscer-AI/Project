import { LoaderFunction, redirect } from "react-router-dom";
import {
  initConversation,
  getConversation,
  getUser,
} from "../../modules/apiCalls";
import {
  TConversationData,
  TChatLoader,
  TUserData,
} from "../../types/chatTypes";

export const chatLoader: LoaderFunction = async ({
  request,
}): Promise<TChatLoader | Response> => {
  let c: TConversationData;
  try {
    const url = new URL(request.url);
    const conversationId = url.searchParams.get("conversation");
    if (conversationId) {
      c = await getConversation(conversationId);
    } else {
      c = await initConversation({ isPublic: false });
    }
    const user = (await getUser()) as TUserData;
    return { conversation: c, user: user };
  } catch (error) {
    console.error("Error loading conversation in chat loader:", error);
    return redirect("/signup");
  }
};
