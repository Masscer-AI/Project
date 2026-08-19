import axios from "axios";

export const validateElevenLabsApiKey = async (apiKey: string) => {
  try {
    const response = await axios.get("https://api.elevenlabs.io/v1/models", {
      headers: {
        "xi-api-key": apiKey,
      },
    });
    return response.status === 200;
  } catch (error) {
    return false;
  }
};

export const listHeyGenAvatars = async (apiKey: string) => {
  try {
    const response = await axios.get("https://api.heygen.com/v2/avatars", {
      headers: {
        "X-Api-Key": apiKey,
      },
    });
    return response.data;
  } catch (error) {
    throw error;
  }
};

export const validateHeyGenApiKey = async (apiKey: string) => {
  try {
    const avatars = await listHeyGenAvatars(apiKey);
    console.log(avatars);
    return true;
  } catch (error) {
    return false;
  }
};
