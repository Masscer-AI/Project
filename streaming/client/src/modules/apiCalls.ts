import axios from "axios";
import { API_URL } from "./constants";

export const initConversation = async () => {
  const endpoint = API_URL + "/v1/messaging/conversations";

  try {
    const token = localStorage.getItem("token");
    if (!token) throw "No token found, impossible to init conversation";

    const response = await axios.post(
      endpoint,
      {},
      {
        headers: {
          Authorization: `Token ${token}`,
        },
      }
    );
    return response.data;
  } catch (error) {
    console.error("Error initiating conversation:", error);
    throw error;
  }
};

export const getConversation = async (conversationId: string) => {
  const endpoint = `${API_URL}/v1/messaging/conversations/${conversationId}`;

  try {
    const token = localStorage.getItem("token");
    if (!token) throw "No token found, impossible to get conversation";

    const response = await axios.get(endpoint, {
      headers: {
        Authorization: `Token ${token}`,
      },
    });
    return response.data;
  } catch (error) {
    console.error("Error fetching conversation:", error);
    throw error;
  }
};
