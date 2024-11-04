import React from "react";
import { Talkie } from "../Talkie/Talkie";
import { API_URL } from "../../modules/constants";
import axios from "axios";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";

// Function to convert Blob to Base64
const convertToBase64 = (file) => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.readAsDataURL(file);
    reader.onload = () => {
      resolve(reader.result); // This will be the Base64 string
    };
    reader.onerror = (error) => {
      reject(error);
    };
  });
};
export const SpeechHandler = ({ onTranscript }) => {

    const {t} = useTranslation()

  const processAudio = async (audioFile: Blob) => {
    toast.success(t("transcribing"))
    const formData = new FormData();
    formData.append("audio_file", audioFile, "audiofile.wav");

    try {
      const response = await axios.post(
        API_URL + "/v1/messaging/upload-audio/",
        formData
      );

      if (response.status === 200) {
        const data = response.data;
        const audioUrl = URL.createObjectURL(audioFile);

        const base64Audio = await convertToBase64(audioFile);
        onTranscript(data.transcription, audioUrl, base64Audio);
      } else {
        console.error("Failed to upload audio file");
      }
    } catch (error) {
      console.error("Error uploading audio file:", error);
    }
  };

  return <Talkie processAudio={processAudio} />;
};
