import React from "react";
import { Talkie } from "../Talkie/Talkie";
import { API_URL } from "../../modules/constants";
import axios from "axios";
import toast from "react-hot-toast";

export const SpeechHandler = () => {
  const processAudio = async (audioFile: Blob) => {
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
        toast.success("Audio uploaded successfully");
        toast.success(data.transcription);
        // setChat((prevChat) => [
        //   ...prevChat,
        //   {
        //     text: data.transcription,
        //     audioSrc: audioUrl,
        //     isUser: true,
        //     type: "user",
        //   },
        // ]);
        // getCompletion(data.transcription);
      } else {
        console.error("Failed to upload audio file");
      }
    } catch (error) {
      console.error("Error uploading audio file:", error);
    }
  };

  return <Talkie processAudio={processAudio} />;
};
