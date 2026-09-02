import { LoaderFunction, redirect } from "react-router-dom";
import axios from "axios";
import {
  initConversation,
  getConversation,
  getUser,
} from "../../modules/apiCalls";
import { TChatLoader, TUserData } from "../../types/chatTypes";
import { TConversation } from "../../types";
import {
  loginUrlWithNext,
  NO_CHAT_HOME_PATH,
  userCanUseChat,
} from "../../utils/loginRedirect";

export const chatLoader: LoaderFunction = async ({
  request,
}): Promise<TChatLoader | Response> => {
  const requestUrl = new URL(request.url);
  let c: TConversation;
  try {
    const conversationId = requestUrl.searchParams.get("conversation");
    const token = requestUrl.searchParams.get("token");
    const query = requestUrl.searchParams.get("query");
    const sendQuery: boolean = requestUrl.searchParams.get("sendQuery") === "true";

    if (token) {
      localStorage.setItem("token", token);
    }
    if (!localStorage.getItem("token")) {
      const returnPath = requestUrl.pathname + requestUrl.search;
      return redirect(loginUrlWithNext(returnPath));
    }

    const canUseChat = await userCanUseChat();
    if (!canUseChat) {
      return redirect(NO_CHAT_HOME_PATH);
    }

    if (conversationId) {
      c = await getConversation(conversationId);
    } else {
      c = await initConversation({ isPublic: false });
      const newUrl = new URL(request.url);
      newUrl.searchParams.set("conversation", c.id);
      return redirect(newUrl.toString());
    }
    const user = (await getUser()) as TUserData;

    return { conversation: c, user: user, query: query, sendQuery };
  } catch (error) {
    console.error("Error loading conversation in chat loader:", error);
    if (axios.isAxiosError(error) && error.response?.status === 403) {
      return redirect(NO_CHAT_HOME_PATH);
    }
    const returnPath = requestUrl.pathname + requestUrl.search;
    return redirect(loginUrlWithNext(returnPath));
  }
};
