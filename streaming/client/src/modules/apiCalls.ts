/* eslint-disable @typescript-eslint/no-explicit-any */
import axios, { AxiosRequestConfig, Method } from "axios";
import { API_URL, PUBLIC_TOKEN } from "./constants";
import {
  TCompletion,
  TConversation,
  TDocument,
  TOrganization,
  TOrganizationCredentials,
  TOrganizationMember,
  TOrganizationRole,
  TRoleAssignment,
  TConversationAlert,
  TAlertStats,
  TConversationAlertRule,
  TTag,
  TWebPage,
  TChatWidget,
} from "../types";
import { TReactionTemplate, TUserProfile } from "../types/chatTypes";
import { TAgent, TModel } from "../types/agents";
import { TUserPreferences } from "./storeTypes";

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
      // DON'T set Content-Type for FormData - axios sets it automatically with the correct boundary
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

type TCreateLlmPayload = {
  provider: string;
  slug: string;
  name: string;
  pricing?: Record<string, any>;
};

export const createLLM = async (data: TCreateLlmPayload) => {
  return makeAuthenticatedRequest<TModel>("POST", "/v1/ai_layers/models/", data, false);
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

// export const getChunk = async (chunkId: string) => {
//   try {
//     const endpoint = `/v1/rag/chunks/${chunkId}/`;
//     const response = await makeAuthenticatedRequest<any>(
//       "GET",
//       endpoint,
//       null,
//       false
//     );
//     return response;
//   } catch (error) {
//     console.error(`Error fetching chunk with ID ${chunkId}:`, error);
//     throw error;
//   }
// };

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

export const getAlerts = async (status?: "all" | "pending" | "notified" | "resolved" | "dismissed") => {
  const endpoint = status && status !== "all" 
    ? `/v1/messaging/alerts?status=${status}`
    : "/v1/messaging/alerts";
  return makeAuthenticatedRequest<TConversationAlert[]>(
    "GET",
    endpoint
  );
};

export const getAlertStats = async () => {
  return makeAuthenticatedRequest<TAlertStats>(
    "GET",
    "/v1/messaging/alerts/stats/"
  );
};

export const updateAlertStatus = async (
  alertId: string,
  status: "PENDING" | "NOTIFIED" | "RESOLVED" | "DISMISSED"
) => {
  return makeAuthenticatedRequest<TConversationAlert>(
    "PUT",
    `/v1/messaging/alerts/${alertId}/`,
    { status }
  );
};

// Alert Rules API functions
export const getAlertRules = async () => {
  return makeAuthenticatedRequest<TConversationAlertRule[]>(
    "GET",
    "/v1/messaging/alert-rules/"
  );
};

export const getAlertRule = async (ruleId: string) => {
  return makeAuthenticatedRequest<TConversationAlertRule>(
    "GET",
    `/v1/messaging/alert-rules/${ruleId}/`
  );
};

export const createAlertRule = async (data: {
  name: string;
  trigger: string;
  extractions?: Record<string, any>;
  scope?: "all_conversations" | "selected_agents";
  enabled?: boolean;
  notify_to?: "all_staff" | "selected_members";
}) => {
  return makeAuthenticatedRequest<TConversationAlertRule>(
    "POST",
    "/v1/messaging/alert-rules/",
    data
  );
};

export const updateAlertRule = async (
  ruleId: string,
  data: Partial<{
    name: string;
    trigger: string;
    extractions: Record<string, any>;
    scope: "all_conversations" | "selected_agents";
    enabled: boolean;
    notify_to: "all_staff" | "selected_members";
  }>
) => {
  return makeAuthenticatedRequest<TConversationAlertRule>(
    "PUT",
    `/v1/messaging/alert-rules/${ruleId}/`,
    data
  );
};

export const deleteAlertRule = async (ruleId: string) => {
  return makeAuthenticatedRequest<{ message: string; status: number }>(
    "DELETE",
    `/v1/messaging/alert-rules/${ruleId}/`
  );
};

// Tags API functions
export const getTags = async () => {
  return makeAuthenticatedRequest<TTag[]>(
    "GET",
    "/v1/messaging/tags/"
  );
};

export const getTag = async (tagId: number) => {
  return makeAuthenticatedRequest<TTag>(
    "GET",
    `/v1/messaging/tags/${tagId}/`
  );
};

export const createTag = async (data: {
  title: string;
  description?: string;
  enabled?: boolean;
}) => {
  return makeAuthenticatedRequest<TTag>(
    "POST",
    "/v1/messaging/tags/",
    data
  );
};

export const updateTag = async (
  tagId: number,
  data: Partial<{
    title: string;
    description: string;
    enabled: boolean;
  }>
) => {
  return makeAuthenticatedRequest<TTag>(
    "PUT",
    `/v1/messaging/tags/${tagId}/`,
    data
  );
};

export const deleteTag = async (tagId: number) => {
  return makeAuthenticatedRequest<{ message: string; status: number }>(
    "DELETE",
    `/v1/messaging/tags/${tagId}/`
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

export const createCompletion = async (data: {
  prompt: string;
  answer: string;
  agent?: number | null;
  approved?: boolean;
}) => {
  return makeAuthenticatedRequest<TCompletion>(
    "POST",
    "/v1/finetuning/completions/",
    data
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

type TGenerateImageResponse = {
  image_url: string;
  image_content_b64: string;
  image_name: string;
};
export const generateImage = async (
  prompt: string,
  message_id: number,
  size: string = "1024x1024",
  model: string = "dall-e-3"
): Promise<TGenerateImageResponse> => {
  return makeAuthenticatedRequest("POST", "/v1/tools/generate_image/", {
    prompt,
    message_id,
    size,
    model,
  });
};

type TPromptNodeData = {
  system_prompt: string;
  model: string;
  user_message: string;
  response_format: "text" | "json";
};

type TPromptNodeResponse = {
  response: string;
};
export const promptNodeAction = async (
  data: TPromptNodeData
): Promise<TPromptNodeResponse> => {
  return makeAuthenticatedRequest("POST", "/v1/tools/prompt_node/", data);
};

export const deleteDocument = async (documentId: number) => {
  return makeAuthenticatedRequest("DELETE", `/v1/rag/documents/${documentId}/`);
};

type TShareConversationResponse = {
  id: string;
};

export const shareConversation = async (
  conversationId: string,
  validUntil: Date | null
) => {
  return makeAuthenticatedRequest<TShareConversationResponse>(
    "POST",
    `/v1/messaging/shared-conversations/`,
    { conversation: conversationId, valid_until: validUntil }
  );
};

export const getSharedConversation = async (id: string) => {
  return makeAuthenticatedRequest(
    "GET",
    `/v1/messaging/shared-conversations/${id}/`,
    null,
    true
  );
};

export const getUserOrganizations = async () => {
  return makeAuthenticatedRequest<TOrganization[]>(
    "GET",
    "/v1/auth/organizations/"
  );
};

type TGenerateDocumentInput = {
  source_text: string;
  from_type: string;
  to_type: string;
};

export const generateDocument = async (data: TGenerateDocumentInput) => {
  return makeAuthenticatedRequest("POST", "/v1/tools/generate_document/", data);
};
export const downloadFile = async (file_path: string) => {
  const { token } = getToken(false);

  const url = `${API_URL}/v1/tools/download/${file_path}/`;

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Authorization: `Token ${token}`,
      },
    });

    // Check if the response is OK
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const blob = await response.blob();
    const link = document.createElement("a");
    link.href = window.URL.createObjectURL(blob);
    // @ts-ignore
    link.download = file_path.split("/").pop();
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    return true;
  } catch (error) {
    console.error("Document download failed: ", error);
    return false;
  }
};

export const getBigDocument = async (documentId: string) => {
  return makeAuthenticatedRequest<TDocument>(
    "GET",
    `/v1/rag/documents/${documentId}/chunks/`
  );
};

export const createRandomAgent = async () => {
  return makeAuthenticatedRequest<TAgent>(
    "POST",
    "/v1/ai_layers/agents/create/random/"
  );
};

export const bulkUpdateCompletions = async (data: TCompletion[]) => {
  return makeAuthenticatedRequest(
    "PUT",
    "/v1/finetuning/bulk/completions/",
    data
  );
};

export const bulkDeleteCompletions = async (ids: number[]) => {
  return makeAuthenticatedRequest(
    "DELETE",
    "/v1/finetuning/bulk/completions/",
    { completions_ids: ids }
  );
};

export const deleteMessage = async (messageId: number) => {
  return makeAuthenticatedRequest(
    "DELETE",
    `/v1/messaging/messages/${messageId}/`
  );
};

export const getUserPreferences = async () => {
  return makeAuthenticatedRequest<TUserPreferences>("GET", "/v1/preferences/");
};

export const updateUserPreferences = async (data: any) => {
  return makeAuthenticatedRequest("PUT", "/v1/preferences/", data);
};

type TEditImageData = {
  image: string;
  prompt: string;
  mask?: string;
  steps?: number;
  prompt_upsampling?: boolean;
  guidance?: number;
  output_format?: string;
  safety_tolerance?: number;
};

export const editImage = async (data: TEditImageData) => {
  return makeAuthenticatedRequest("POST", "/v1/tools/image_editor/", data);
};

type TUpdateUserData = {
  username: string;
  email: string;
  profile?: TUserProfile;
  current_password?: string;
  new_password?: string;
};

export const updateUser = async (data: TUpdateUserData) => {
  return makeAuthenticatedRequest("PUT", "/v1/auth/user/me", data);
};

type TFetchUrlContentResponse = {
  content: string;
};

export const fetchUrlContent = async (url: string) => {
  return makeAuthenticatedRequest<TFetchUrlContentResponse>(
    "POST",
    "/v1/tools/website_fetcher/",
    {
      url,
    }
  );
};


export const generateDocumentBrief = async (documentId: string) => {
  return makeAuthenticatedRequest("PUT", `/v1/rag/documents/${documentId}/`, {
    action: "generate_brief",
  });
};

type TCreateWebPagePayload = {
  url: string;
  title?: string;
  is_pinned?: boolean;
};

type TUpdateWebPagePayload = Partial<TCreateWebPagePayload>;

export const getWebPages = async (pinned?: boolean) => {
  const params = pinned ? "?pinned=true" : "";
  return makeAuthenticatedRequest<TWebPage[]>(
    "GET",
    `/v1/preferences/webpages/${params}`
  );
};

export const createWebPage = async (data: TCreateWebPagePayload) => {
  return makeAuthenticatedRequest<TWebPage>(
    "POST",
    "/v1/preferences/webpages/",
    data
  );
};

export const updateWebPage = async (id: number, data: TUpdateWebPagePayload) => {
  return makeAuthenticatedRequest<TWebPage>(
    "PATCH",
    `/v1/preferences/webpages/${id}/`,
    data
  );
};

export const deleteWebPage = async (id: number) => {
  return makeAuthenticatedRequest<{ deleted: boolean }>(
    "DELETE",
    `/v1/preferences/webpages/${id}/`
  );
};

type TGenerateVideoData = {
  prompt: string;
  image_b64: string;
  message_id: number;
  ratio: string;
};
export const generateVideo = async (data: TGenerateVideoData) => {
  return makeAuthenticatedRequest(
    "POST",
    "/v1/tools/video_generator/image_to_video/",
    data
  );
};

export type TOrganizationData = {
  name: string;
  description: string;
};

export type TUpdateOrganizationOptions = {
  logoFile?: File;
  deleteLogo?: boolean;
};

export const createOrganization = async (data: TOrganizationData) => {
  return makeAuthenticatedRequest("POST", "/v1/auth/organizations/", data);
};

export const deleteOrganization = async (organizationId: string) => {
  return makeAuthenticatedRequest(
    "DELETE",
    `/v1/auth/organizations/${organizationId}/`
  );
};

export const getOrganizationCredentials = async (organizationId: string) => {
  return makeAuthenticatedRequest<TOrganizationCredentials>(
    "GET",
    `/v1/auth/organizations/${organizationId}/credentials/`
  );
};

export const getOrganizationMembers = async (organizationId: string) => {
  return makeAuthenticatedRequest<TOrganizationMember[]>(
    "GET",
    `/v1/auth/organizations/${organizationId}/members/`
  );
};

export const getOrganizationRoles = async (organizationId: string) => {
  return makeAuthenticatedRequest<TOrganizationRole[]>(
    "GET",
    `/v1/auth/organizations/${organizationId}/roles/`
  );
};

export const createOrganizationRole = async (
  organizationId: string,
  data: { name: string; description?: string; enabled?: boolean; capabilities?: string[] }
) => {
  return makeAuthenticatedRequest<TOrganizationRole>(
    "POST",
    `/v1/auth/organizations/${organizationId}/roles/`,
    data
  );
};

export const updateOrganizationRole = async (
  organizationId: string,
  roleId: string,
  data: Partial<{ name: string; description: string; enabled: boolean; capabilities: string[] }>
) => {
  return makeAuthenticatedRequest<TOrganizationRole>(
    "PUT",
    `/v1/auth/organizations/${organizationId}/roles/${roleId}/`,
    data
  );
};

export const deleteOrganizationRole = async (organizationId: string, roleId: string) => {
  return makeAuthenticatedRequest<{ message: string }>(
    "DELETE",
    `/v1/auth/organizations/${organizationId}/roles/${roleId}/`
  );
};

export const getOrganizationRoleAssignments = async (organizationId: string) => {
  return makeAuthenticatedRequest<(TRoleAssignment & { user_id?: number })[]>(
    "GET",
    `/v1/auth/organizations/${organizationId}/roles/assignments/`
  );
};

export const assignRoleToMember = async (
  organizationId: string,
  data: { user_id: number; role_id: string }
) => {
  return makeAuthenticatedRequest<TRoleAssignment>(
    "POST",
    `/v1/auth/organizations/${organizationId}/roles/assignments/`,
    data
  );
};

export const removeRoleAssignment = async (
  organizationId: string,
  assignmentId: string
) => {
  return makeAuthenticatedRequest<{ message: string }>(
    "DELETE",
    `/v1/auth/organizations/${organizationId}/roles/assignments/?assignment_id=${assignmentId}`
  );
};

export const deactivateOrganizationMember = async (
  organizationId: string,
  userId: number,
  isActive: boolean
) => {
  return makeAuthenticatedRequest<{ message: string; is_active: boolean }>(
    "PATCH",
    `/v1/auth/organizations/${organizationId}/members/${userId}/`,
    { is_active: isActive }
  );
};

export const removeOrganizationMember = async (
  organizationId: string,
  userId: number
) => {
  return makeAuthenticatedRequest<{ message: string }>(
    "DELETE",
    `/v1/auth/organizations/${organizationId}/members/${userId}/`
  );
};

export type TFeatureFlagInfo = {
  name: string;
  organization_only: boolean;
};

export const getFeatureFlagNames = async () => {
  return makeAuthenticatedRequest<TFeatureFlagInfo[]>("GET", "/v1/auth/feature-flags/names/");
};

export const updateOrganizationCredentials = async (
  organizationId: string,
  data: TOrganizationCredentials
) => {
  return makeAuthenticatedRequest(
    "PUT",
    `/v1/auth/organizations/${organizationId}/credentials/`,
    data
  );
};

export const updateOrganization = async (
  organizationId: string,
  data: TOrganizationData,
  options?: TUpdateOrganizationOptions
): Promise<TOrganization> => {
  // Determine if we need to send FormData (for file upload or delete)
  const hasLogoFile = options?.logoFile instanceof File;
  const shouldDeleteLogo = options?.deleteLogo === true;
  const needsFormData = hasLogoFile || shouldDeleteLogo;
  
  console.log("🔄 updateOrganization:", {
    organizationId,
    name: data.name,
    hasLogoFile,
    shouldDeleteLogo,
    needsFormData,
    logoFileName: options?.logoFile?.name,
  });
  
  if (needsFormData) {
    const formData = new FormData();
    formData.append("name", data.name ?? "");
    formData.append("description", data.description ?? "");
    formData.append("delete_logo", shouldDeleteLogo ? "true" : "false");
    
    if (hasLogoFile && options.logoFile) {
      formData.append("logo", options.logoFile);
      console.log("📎 Added logo to FormData:", options.logoFile.name, options.logoFile.size, "bytes");
    }
    
    // Debug: log all FormData entries
    console.log("📦 FormData contents:");
    for (const [key, value] of formData.entries()) {
      if (value instanceof File) {
        console.log(`  ${key}: File("${value.name}", ${value.size} bytes, ${value.type})`);
      } else {
        console.log(`  ${key}: "${value}"`);
      }
    }
    
    return makeAuthenticatedRequest<TOrganization>(
      "PUT",
      `/v1/auth/organizations/${organizationId}/`,
      formData
    );
  }
  
  // No logo changes, send JSON
  return makeAuthenticatedRequest<TOrganization>(
    "PUT",
    `/v1/auth/organizations/${organizationId}/`,
    data
  );
};

export const deleteTranscriptionJob = async (jobId: number) => {
  return makeAuthenticatedRequest(
    "DELETE",
    `/v1/tools/transcriptions/${jobId}/`
  );
};

export type TVoice = {
  id: string;
  name: string;
  provider: string;
};

type TGenerateAudioData = {
  text: string;
  voice: TVoice;
  message_id: string;
};

export const generateAudio = async (data: TGenerateAudioData) => {
  return makeAuthenticatedRequest("POST", "/v1/tools/audio_generator/", data);
};

export const getUserVoices = async () => {
  return makeAuthenticatedRequest<TVoice[]>("GET", "/v1/preferences/voices/");
};

export const updateUserVoices = async (data: TVoice[]) => {
  return makeAuthenticatedRequest("PUT", "/v1/preferences/voices/", data);
};

export type FeatureFlagStatusResponse = {
  enabled: boolean;
  feature_flag_name: string;
  reason: string;
};

export type TeamFeatureFlagsResponse = {
  feature_flags: Record<string, boolean>;
};

export const checkFeatureFlag = async (
  featureFlagName: string
): Promise<FeatureFlagStatusResponse> => {
  return makeAuthenticatedRequest<FeatureFlagStatusResponse>(
    "GET",
    `/v1/auth/feature-flags/${featureFlagName}/check`
  );
};

export const getTeamFeatureFlags = async (): Promise<TeamFeatureFlagsResponse> => {
  return makeAuthenticatedRequest<TeamFeatureFlagsResponse>(
    "GET",
    "/v1/auth/feature-flags/"
  );
};

// Chat Widget API functions
export const getChatWidgets = async () => {
  return makeAuthenticatedRequest<TChatWidget[]>(
    "GET",
    "/v1/messaging/widgets/"
  );
};

export const getChatWidget = async (widgetId: number) => {
  return makeAuthenticatedRequest<TChatWidget>(
    "GET",
    `/v1/messaging/widgets/${widgetId}/`
  );
};

export const createChatWidget = async (data: {
  name: string;
  agent_id?: number | null;
  enabled?: boolean;
  web_search_enabled?: boolean;
  rag_enabled?: boolean;
  plugins_enabled?: string[];
}) => {
  return makeAuthenticatedRequest<TChatWidget>(
    "POST",
    "/v1/messaging/widgets/",
    data
  );
};

export const updateChatWidget = async (
  widgetId: number,
  data: Partial<{
    name: string;
    agent_id: number | null;
    enabled: boolean;
    web_search_enabled: boolean;
    rag_enabled: boolean;
    plugins_enabled: string[];
  }>
) => {
  return makeAuthenticatedRequest<TChatWidget>(
    "PUT",
    `/v1/messaging/widgets/${widgetId}/`,
    data
  );
};

export const deleteChatWidget = async (widgetId: number) => {
  return makeAuthenticatedRequest<{ message: string; status: number }>(
    "DELETE",
    `/v1/messaging/widgets/${widgetId}/`
  );
};

// ---- Agent Task ----

export type TAgentTaskInput =
  | { type: "input_text"; text: string }
  | { type: "input_image"; content: string }
  | { type: "input_document"; content: string; name?: string };

export type TriggerAgentTaskPayload = {
  conversation_id: string;
  agent_slug: string;
  user_inputs: TAgentTaskInput[];
  tool_names?: string[];
};

export type TriggerAgentTaskResponse = {
  task_id: string;
  status: string;
};

export const triggerAgentTask = async (payload: TriggerAgentTaskPayload) => {
  return makeAuthenticatedRequest<TriggerAgentTaskResponse>(
    "POST",
    "/v1/ai_layers/agent-task/conversation/",
    payload
  );
};

