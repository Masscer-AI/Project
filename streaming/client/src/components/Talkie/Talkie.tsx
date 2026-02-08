import React, { useRef, useEffect, useState } from "react";
import { useHotkeys } from "react-hotkeys-hook";
import { ActionIcon } from "@mantine/core";
import { IconMicrophone, IconPlayerStop } from "@tabler/icons-react";

interface TalkieProps {
  processAudio: (audioFile: Blob, transcription: string) => void;
}

export const Talkie: React.FC<TalkieProps> = ({ processAudio }) => {
  const [isRecording, setIsRecording] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const transcriptionRef = useRef<string>("");

  const startRecording = async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorderRef.current = mediaRecorder;

    mediaRecorder.ondataavailable = (event) => {
      audioChunksRef.current.push(event.data);
    };

    mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(audioChunksRef.current, {
        type: "audio/wav",
      });
      processAudio(audioBlob, transcriptionRef.current);
      audioChunksRef.current = [];
      transcriptionRef.current = "";
    };

    mediaRecorder.start();
    setIsRecording(true);
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  useEffect(() => {
    if (isRecording) {
      // @ts-ignore
      const recognition = new (window.SpeechRecognition ||
        // @ts-ignore
        window.webkitSpeechRecognition)();
      recognition.continuous = true;
      recognition.interimResults = true;

      recognition.onresult = (event: any) => {
        let interimTranscription = "";
        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            transcriptionRef.current += transcript;
          } else {
            interimTranscription += transcript;
          }
        }
      };

      recognition.start();

      return () => {
        recognition.stop();
      };
    }
  }, [isRecording]);

  useHotkeys(
    "ctrl+alt+r",
    () => {
      if (isRecording) {
        stopRecording();
      } else {
        startRecording();
      }
    },
    {
      enableOnFormTags: true,
    }
  );

  return (
    <ActionIcon
      variant={isRecording ? "filled" : "subtle"}
      color={isRecording ? "red" : "gray"}
      size="lg"
      radius="xl"
      onClick={isRecording ? stopRecording : startRecording}
      aria-label={isRecording ? "Stop recording" : "Start recording"}
    >
      {isRecording ? (
        <IconPlayerStop size={20} />
      ) : (
        <IconMicrophone size={20} />
      )}
    </ActionIcon>
  );
};
