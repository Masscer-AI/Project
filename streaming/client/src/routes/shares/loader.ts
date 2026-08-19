import { getSharedConversation } from "../../modules/apiCalls";

export const sharesLoader = async () => {
  const params = new URLSearchParams(window.location.search);
  try {
    const data = await getSharedConversation(params.get("id") as string);
    console.log(data);
    return data;
  } catch (e) {
    console.log(e);
  }
  return null;
};
