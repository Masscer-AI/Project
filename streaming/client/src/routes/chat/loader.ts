import { LoaderFunction, redirect } from "react-router-dom";
import {
  initConversation,
  getConversation,
  getUser,
} from "../../modules/apiCalls";
import { TChatLoader, TUserData } from "../../types/chatTypes";
import { TConversation } from "../../types";

export const chatLoader: LoaderFunction = async ({
  request,
}): Promise<TChatLoader | Response> => {
  let c: TConversation;
  try {
    const url = new URL(request.url);
    const conversationId = url.searchParams.get("conversation");
    const token = url.searchParams.get("token");
    const query = url.searchParams.get("query");
    const sendQuery: boolean = url.searchParams.get("sendQuery") === "true";

    if (token) {
      localStorage.setItem("token", token);
    }

    if (conversationId) {
      c = await getConversation(conversationId);
    } else {
      c = await initConversation({ isPublic: false });
    }
    const user = (await getUser()) as TUserData;
    // console.log(query, "query");

    return { conversation: c, user: user, query: query, sendQuery };
  } catch (error) {
    console.error("Error loading conversation in chat loader:", error);
    return redirect("/login");
  }
};
