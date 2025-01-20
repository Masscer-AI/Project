import axios from "axios";

// curl 'https://api.elevenlabs.io/v1/models' \
//   -H 'Content-Type: application/json' \
//   -H 'xi-api-key: $ELEVENLABS_API_KEY'

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

// curl --request GET \
//      --url https://api.heygen.com/v2/avatars \
//      --header 'Accept: application/json' \
//      --header 'X-Api-Key: <your-api-key>'

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
