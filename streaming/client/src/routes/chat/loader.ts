import { LoaderFunction, redirect } from "react-router-dom"
import { initConversation, getConversation } from "../../modules/apiCalls"
import { TConversationData } from "../../types/chatTypes"

export const chatLoader: LoaderFunction = async ({
  params,
}): Promise<{ conversation: TConversationData } | Response> => {
  let c: TConversationData
  try {
    console.log("Loading page!");
    

    if (params.conversationId) {
      c = await getConversation(params.conversationId)
    } else {
      c = await initConversation()
    }

    return { conversation: c }
  } catch (error) {
    console.error("Error loading conversation:", error)
    return redirect("/signup")
  }
}
