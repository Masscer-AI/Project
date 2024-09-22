import React, { useState, useEffect } from "react";
import { Navbar } from "../../components/Navbar/Navbar";
import { Talkie } from "../../components/Talkie/Talkie";
import { ChatItem, TSomething } from "../../types";
import { ChatMessages } from "../../components/Messages/Messages";

import io from "socket.io-client";
import { useLoaderData } from "react-router-dom";
import { PUBLIC_TOKEN } from "../../modules/constants";
// import { SpeechReceptor } from "../../components/SpeechReceptor/SpeechReceptor";

const socket = io("http://localhost:8001", { autoConnect: true });

export default function Root() {
  const data = useLoaderData() as { conversation: TSomething };

  const [chat, setChat] = useState<ChatItem[]>([]);

  useEffect(() => {
    socket.on("connect", () => {
      console.log("Connected to socket server");
    });

    socket.on("disconnect", () => {
      console.log("Disconnected from socket server");
    });

    const updateMessages = (chunk: string) => {
      const newMessages = [...chat];
      const lastMessage = newMessages[newMessages.length - 1];

      if (lastMessage && lastMessage.isUser === false) {
        lastMessage.text += chunk;
      } else {
        const assistantMessage = {
          text: chunk,
          isUser: false,
        };
        newMessages.push(assistantMessage);
      }
      return newMessages;
    };

    socket.on("response", (data) => {
      setChat(updateMessages(data.chunk));
    });

    socket.on("responseFinished", (data) => {
      console.log("Response finished:", data);
      generateSpeech(data.ai_response);
      // socket.disconnect();
    });

    socket.on("audio-file", (audioFile) => {
      const audioBlob = new Blob([audioFile], { type: "audio/mp3" });
      saveSpeechToMessage(audioBlob);
    });

    return () => {
      socket.off("connect");
      socket.off("disconnect");
      socket.off("response");
      socket.off("responseFinished");
      socket.off("audio-file");
    };
  }, [chat]);

  const processAudioExample = async (audioFile: Blob) => {
    const formData = new FormData();
    formData.append("file", audioFile, "audiofile.wav");

    try {
      const response = await fetch("/upload-audio/", {
        method: "POST",
        body: formData,
      });

      if (response.ok) {
        const data = await response.json();
        const audioUrl = URL.createObjectURL(audioFile);
        setChat((prevChat) => [
          ...prevChat,
          { text: data.transcription, audioSrc: audioUrl, isUser: true },
        ]);
        getCompletion(data.transcription);
      } else {
        console.error("Failed to upload audio file");
      }
    } catch (error) {
      console.error("Error uploading audio file:", error);
    }
  };

  const getCompletion = (transcription: string) => {
    const context = chat
      .slice(-6)
      .map((item) => `${item.isUser ? "user" : "ai"}: ${item.text}`)
      .join("\n");

    socket.connect();
    socket.emit("message", {
      message: transcription,
      context,
      conversation: data.conversation,
      token: PUBLIC_TOKEN,
    });
  };

  const generateSpeech = async (text: string) => {
    socket.emit("speech_request", {
      text,
    });
  };

  const saveSpeechToMessage = (audioFile: Blob) => {
    setChat((prevChat) => {
      const newMessages = [...prevChat];
      const lastMessage = newMessages[newMessages.length - 1];
      console.log(lastMessage, "LAST MESSAGE!");

      const audioUrl = URL.createObjectURL(audioFile);
      lastMessage.audioSrc = audioUrl;

      return newMessages;
    });
  };

  return (
    <>
      <Navbar />
      {/* <SpeechReceptor socket={socket} /> */}
      <ChatMessages chat={chat} />
      <Talkie processAudio={processAudioExample} />
    </>
  );
}
