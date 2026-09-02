import { LoaderFunction, redirect } from "react-router-dom";
import axios from "axios";
import { getOrCreateComplianceConversation, getUser } from "../../modules/apiCalls";
import { TChatLoader, TUserData } from "../../types/chatTypes";
import { loginUrlWithNext, AUTH_HOME_PATH, userHasTeamFeature } from "../../utils/loginRedirect";

export const complianceLoader: LoaderFunction = async ({
  request,
}): Promise<TChatLoader | Response> => {
  const requestUrl = new URL(request.url);
  try {
    if (!localStorage.getItem("token")) {
      const returnPath = requestUrl.pathname + requestUrl.search;
      return redirect(loginUrlWithNext(returnPath));
    }
    const canAccess = await userHasTeamFeature("organization-compliance-access");
    if (!canAccess) {
      return redirect(AUTH_HOME_PATH);
    }
    const conversation = await getOrCreateComplianceConversation();
    const user = (await getUser()) as TUserData;
    return { conversation, user, query: null, sendQuery: false };
  } catch (error) {
    console.error("Error loading compliance conversation:", error);
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return redirect(AUTH_HOME_PATH);
    }
    const returnPath = requestUrl.pathname + requestUrl.search;
    return redirect(loginUrlWithNext(returnPath));
  }
};
