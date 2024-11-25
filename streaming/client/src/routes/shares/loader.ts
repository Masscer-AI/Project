import { getSharedConversation } from "../../modules/apiCalls";

export const sharesLoader = async () => {
  // get the query params
  const params = new URLSearchParams(window.location.search);
  try {
    const data = await getSharedConversation(params.get("id") as string);
    // toast.success("loading shares");
    console.log(data);
    return data;
  } catch (e) {
    console.log(e);
  }
  return null;
};
