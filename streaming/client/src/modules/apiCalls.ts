/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, { AxiosRequestConfig, Method } from "axios";
import { API_URL, PUBLIC_TOKEN } from "./constants";

const getToken = (isPublic: boolean) => {
  if (isPublic) {
    return { token: PUBLIC_TOKEN, tokenType: "PublishToken" };
  } else {
    const token = localStorage.getItem("token");
    if (!token) throw new Error("No token found, impossible to make request");
    return { token, tokenType: "Token" };
  }
};

export const initConversation = async ({ isPublic = false }) => {
  const endpoint = API_URL + "/v1/messaging/conversations";

  try {
    const { token, tokenType } = isPublic
      ? { token: PUBLIC_TOKEN, tokenType: "PublishToken" }
      : { token: localStorage.getItem("token"), tokenType: "Token" };

    if (!token) throw Error("No token found, impossible to init conversation");

    const response = await axios.post(
      endpoint,
      {},
      {
        headers: {
          Authorization: `${tokenType} ${token}`,
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

export const makeAuthenticatedRequest = async <T>(
  method: Method,
  endpoint: string,
  data: any = {},
  isPublic: boolean = false
) => {
  const { token, tokenType } = getToken(isPublic);

  const config: AxiosRequestConfig = {
    method,
    url: `${API_URL}${endpoint}`,
    headers: {
      Authorization: `${tokenType} ${token}`,
    },
    data,
  };

  try {
    const response = await axios(config);
    return response.data as T;
  } catch (error) {
    console.error(`Error making ${method} request to ${endpoint}:`, error);
    throw error;
  }
};
