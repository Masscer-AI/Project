/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, { AxiosRequestConfig, Method } from "axios";
import { API_URL, PUBLIC_TOKEN } from "./constants";
import { TCompletion, TConversation } from "../types";
import { TReactionTemplate } from "../types/chatTypes";

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
  const endpoint = `${API_URL}/v1/messaging/conversations/${conversationId}/`;

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

  if (endpoint.startsWith("/")) {
    endpoint = endpoint.slice(1);
  }

  const config: AxiosRequestConfig = {
    method,
    url: `${API_URL}/${endpoint}`,
    headers: {
      Authorization: `${tokenType} ${token}`,
      ...(data instanceof FormData
        ? { "Content-Type": "multipart/form-data" }
        : {}),
    },
    data,
  };

  try {
    const response = await axios(config);
    if (method === "DELETE") {
      console.log(response.data, "RESPONSE DATA");
    }
    return response.data as T;
  } catch (error) {
    console.error(`Error making ${method} request to ${endpoint}:`, error);
    throw error;
  }
};

interface AgentsResponseData {
  agents: any[];
  models: any[];
}
export const getAgents = async (isPublic: boolean = false) => {
  try {
    const res = await makeAuthenticatedRequest<AgentsResponseData>(
      "GET",
      "/v1/ai_layers/agents/",
      {},
      isPublic
    );
    return res;
  } catch (error) {
    console.error("Error fetching agents:", error);
    throw error;
  }
};

export const uploadDocument = async (documentData: FormData) => {
  try {
    const response = await makeAuthenticatedRequest<any>(
      "POST",
      "/v1/rag/documents/",
      documentData,
      false
    );
    return response;
  } catch (error) {
    console.error("Error uploading document:", error);
    throw error;
  }
};
export const getDocuments = async () => {
  try {
    const response = await makeAuthenticatedRequest<any>(
      "GET",
      "/v1/rag/documents/",
      null,
      false
    );
    return response;
  } catch (error) {
    console.error("Error uploading document:", error);
    throw error;
  }
};

export const requestVideoGeneration = async (about, duration, orientation) => {
  try {
    const data = { about, duration, orientation };
    const response = await makeAuthenticatedRequest(
      "POST",
      "/v1/tools/videos/",
      data,
      false
    );
    return response;
  } catch (error) {
    console.error("Error requesting video generation:", error);
    throw error;
  }
};

export const updateAgent = async (agentSlug: string, updatedData: any) => {
  try {
    const endpoint = `/v1/ai_layers/agents/${agentSlug}/`;

    const response = await makeAuthenticatedRequest<any>(
      "PUT",
      endpoint,
      updatedData,
      false
    );

    return response;
  } catch (error) {
    console.error("Error updating agent:", error);
    throw error;
  }
};

export const getUser = async () => {
  return makeAuthenticatedRequest("GET", "v1/auth/user/me");
};

export const createAgent = async (agent: any) => {
  try {
    const endpoint = `/v1/ai_layers/agents/`;

    const response = await makeAuthenticatedRequest<any>(
      "POST",
      endpoint,
      agent,
      false
    );

    return response;
  } catch (error) {
    console.error("Error updating agent:", error);
    throw error;
  }
};

export const getChunk = async (chunkId: string) => {
  try {
    const endpoint = `/v1/rag/chunks/${chunkId}/`;
    const response = await makeAuthenticatedRequest<any>(
      "GET",
      endpoint,
      null,
      false
    );
    return response;
  } catch (error) {
    console.error(`Error fetching chunk with ID ${chunkId}:`, error);
    throw error;
  }
};

export const getVideos = async () => {
  try {
    const response = await makeAuthenticatedRequest<any>(
      "GET",
      "/v1/tools/videos/",
      null,
      false
    );
    return response;
  } catch (error) {
    console.error("Error fetching videos:", error);
    throw error;
  }
};

export const getMedia = async (
  query: string,
  perPage: number = 15,
  page: number = 1,
  orientation: string = "landscape",
  isPublic: boolean = false
) => {
  try {
    const endpoint = `/v1/tools/media/?query=${encodeURIComponent(query)}&per_page=${perPage}&page=${page}&orientation=${encodeURIComponent(orientation)}`;
    const response = await makeAuthenticatedRequest<any>(
      "GET",
      endpoint,
      null,
      isPublic
    );
    return response;
  } catch (error) {
    console.error("Error fetching media:", error);
    throw error;
  }
};

export const getWhatsappNumbers = async () => {
  return makeAuthenticatedRequest("GET", "/v1/whatsapp/numbers");
};

export const getWhatsappConversations = async () => {
  return makeAuthenticatedRequest("GET", "/v1/whatsapp/conversations");
};

export const getWhatsappConversationMessages = async (
  conversationId: string
) => {
  return makeAuthenticatedRequest(
    "GET",
    `/v1/whatsapp/conversations/${conversationId}`
  );
};

export const sendMessageToConversation = async (
  conversationId: string,
  message: string
) => {
  return makeAuthenticatedRequest(
    "POST",
    `/v1/whatsapp/conversations/${conversationId}`,
    { message }
  );
};

export const updateWhatsappNumber = async (numberId: string, data: any) => {
  return makeAuthenticatedRequest(
    "PUT",
    `/v1/whatsapp/numbers/${numberId}`,
    data
  );
};

export const deleteAgent = async (slug: string) => {
  return makeAuthenticatedRequest("DELETE", `/v1/ai_layers/agents/${slug}/`);
};

export const deleteConversation = async (conversationId: string) => {
  return makeAuthenticatedRequest(
    "DELETE",
    `/v1/messaging/conversations/${conversationId}/`
  );
};

export const getAllConversations = async () => {
  return makeAuthenticatedRequest<TConversation[]>(
    "GET",
    "/v1/messaging/conversations"
  );
};

interface GenerateTrainingDataRequest {
  model_id: string;
  db_model: "conversation" | "document";
  agents: string[];
  completions_target_number?: number;
  only_prompt?: boolean;
}
export const generateTrainingCompletions = async ({
  model_id,
  db_model,
  agents,
  completions_target_number = 30,
  only_prompt = false,
}: GenerateTrainingDataRequest) => {
  return makeAuthenticatedRequest("POST", "/v1/finetuning/generate/", {
    model_id,
    db_model,
    agents,
    completions_target_number,
    only_prompt,
  });
};

export const getUserCompletions = async () => {
  return makeAuthenticatedRequest<TCompletion[]>(
    "GET",
    "/v1/finetuning/completions/"
  );
};

export const updateCompletion = async (completionId: string, data: any) => {
  return makeAuthenticatedRequest(
    "PUT",
    `/v1/finetuning/completions/${completionId}/`,
    data
  );
};

export const deleteCompletion = async (completionId: string) => {
  return makeAuthenticatedRequest(
    "DELETE",
    `/v1/finetuning/completions/${completionId}/`
  );
};

export const updateConversation = async (conversationId: string, data: any) => {
  return makeAuthenticatedRequest(
    "PUT",
    `/v1/messaging/conversations/${conversationId}/`,
    data
  );
};

type TSuggestionResponse = {
  suggestion: string;
};

export const getSuggestion = async (input: string) => {
  return makeAuthenticatedRequest<TSuggestionResponse>(
    "POST",
    "/v1/messaging/get-suggestion/",
    {
      input,
    }
  );
};

export const updateMessage = async (messageId: number, data: any) => {
  return makeAuthenticatedRequest(
    "PUT",
    `/v1/messaging/messages/${messageId}/`,
    data
  );
};

export const getReactionTemplates = async () => {
  return makeAuthenticatedRequest<TReactionTemplate[]>(
    "GET",
    "/v1/feedback/reaction-templates/"
  );
};

type TCreateReactionData = {
  conversation?: string;
  template: string;
  message?: string;
};
export const createReaction = async (data: TCreateReactionData) => {
  return makeAuthenticatedRequest("POST", "/v1/feedback/reactions/", data);
};
