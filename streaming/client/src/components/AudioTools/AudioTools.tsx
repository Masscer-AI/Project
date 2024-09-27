import React, { useState, useRef } from "react";
import axios from "axios";
import { API_URL } from "../../modules/constants";
import "./AudioTools.css";
interface AudioOptionsProps {
  selectedOption: string;
  handleOptionClick: (option: string) => void;
}

const AudioOptions: React.FC<AudioOptionsProps> = ({
  selectedOption,
  handleOptionClick,
}) => (
  <section>
    <button
      className={`button ${selectedOption === "transcribe" ? "selected" : ""}`}
      onClick={() => handleOptionClick("transcribe")}
    >
      Transcribe
    </button>
    <button
      className={`button ${selectedOption === "podcast" ? "selected" : ""}`}
      onClick={() => handleOptionClick("podcast")}
    >
      Generate Podcast
    </button>
    <button
      className={`button ${selectedOption === "music" ? "selected" : ""}`}
      onClick={() => handleOptionClick("music")}
    >
      Generate Music
    </button>
  </section>
);

interface TranscribeOptionsProps {
  selectedOption: string;
  handleOptionClick: (option: string) => void;
  handleSubmit: (
    selectedOption: string,
    youtubeUrl: string,
    audioFile: File | null,
    recordedBlob: Blob | null
  ) => void;
}
const TranscribeOptions: React.FC<TranscribeOptionsProps> = ({
  selectedOption,
  handleOptionClick,
  handleSubmit,
}) => {
  const [youtubeUrl, setYoutubeUrl] = useState<string>("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [recording, setRecording] = useState<boolean>(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    setRecording(true);
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mediaRecorder = new MediaRecorder(stream);
    mediaRecorderRef.current = mediaRecorder;
    chunksRef.current = [];

    mediaRecorder.ondataavailable = (e) => chunksRef.current.push(e.data);
    mediaRecorder.onstop = () => {
      const blob = new Blob(chunksRef.current, { type: "audio/wav" });
      setRecordedBlob(blob);
      setAudioUrl(URL.createObjectURL(blob));
      setRecording(false);
    };

    mediaRecorder.start();
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current) {
      mediaRecorderRef.current.stop();
    }
  };

  const pauseRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "recording"
    ) {
      mediaRecorderRef.current.pause();
    }
  };

  const resumeRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "paused"
    ) {
      mediaRecorderRef.current.resume();
    }
  };

  const handleFileChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files ? e.target.files[0] : null;
    if (file) {
      setAudioFile(file);
      setAudioUrl(URL.createObjectURL(file));
    }
  };

  return (
    <div>
      <h5>From:</h5>
      <div>
        <button
          className={`button ${selectedOption === "youtube" ? "selected" : ""}`}
          onClick={() => handleOptionClick("youtube")}
        >
          YouTube URL
        </button>
        <button
          className={`button ${selectedOption === "microphone" ? "selected" : ""}`}
          onClick={() => handleOptionClick("microphone")}
        >
          Microphone
        </button>
        <button
          className={`button ${selectedOption === "audio" ? "selected" : ""}`}
          onClick={() => handleOptionClick("audio")}
        >
          Audio/Video File
        </button>
      </div>
      {selectedOption === "youtube" && (
        <input
          type="text"
          placeholder="Enter YouTube URL"
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
        />
      )}
      {selectedOption === "microphone" && (
        <>
          <button onClick={startRecording} disabled={recording}>
            {recording ? "Recording..." : "Start Recording"}
          </button>
          <button
            onClick={pauseRecording}
            disabled={
              !recording || mediaRecorderRef.current?.state === "paused"
            }
          >
            Pause
          </button>
          <button
            onClick={resumeRecording}
            disabled={
              !recording || mediaRecorderRef.current?.state !== "paused"
            }
          >
            Resume
          </button>
          <button onClick={stopRecording} disabled={!recording}>
            Stop
          </button>
          {recordedBlob && <p>Recording complete</p>}
        </>
      )}
      {selectedOption === "audio" && (
        <input
          type="file"
          accept="audio/*,video/*"
          onChange={handleFileChange}
        />
      )}
      {audioUrl && <audio controls src={audioUrl}></audio>}
      {selectedOption && (
        <button
          onClick={() =>
            handleSubmit(selectedOption, youtubeUrl, audioFile, recordedBlob)
          }
        >
          Transcribe
        </button>
      )}
    </div>
  );
};

export const AudioTools: React.FC = () => {
  const [audioOption, setAudioOption] = useState<string>("");
  const [transcribeOption, setTranscribeOption] = useState<string>("");

  const handleAudioOption = (option: string) => {
    setAudioOption(option);
    setTranscribeOption("");
  };

  const handleSubmit = async (
    selectedOption: string,
    youtubeUrl: string,
    audioFile: File | null,
    recordedBlob: Blob | null
  ) => {
    const formData = new FormData();
    if (selectedOption === "youtube") {
      formData.append("source", "youtube_url");
      formData.append("youtube_url", youtubeUrl);
    } else if (selectedOption === "audio" && audioFile) {
      const fileType = audioFile.type.startsWith("video/") ? "video" : "audio";
      formData.append("source", fileType);
      formData.append(`${fileType}_file`, audioFile);
    } else if (selectedOption === "microphone" && recordedBlob) {
      formData.append("source", "audio");
      formData.append("audio_file", recordedBlob, "recording.wav");
    }

    try {
      const response = await axios.post(
        `${API_URL}/v1/tools/transcriptions/`,
        formData,
        {
          headers: {
            "Content-Type": "multipart/form-data",
          },
        }
      );
      console.log(response.data);
    } catch (error) {
      console.error("Error:", error);
    }
  };

  return (
    <div className="audio-tools">
      <h4>What do you want to do with audio?</h4>
      <AudioOptions
        selectedOption={audioOption}
        handleOptionClick={handleAudioOption}
      />
      {audioOption === "transcribe" && (
        <TranscribeOptions
          selectedOption={transcribeOption}
          handleOptionClick={setTranscribeOption}
          handleSubmit={handleSubmit}
        />
      )}
    </div>
  );
};
