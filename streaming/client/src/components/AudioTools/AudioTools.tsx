import React, { useState, useRef, useEffect } from "react";
import "./AudioTools.css";
import toast from "react-hot-toast";
import {
  deleteTranscriptionJob,
  makeAuthenticatedRequest,
} from "../../modules/apiCalls";

import { Modal } from "../Modal/Modal";
import { useTranslation } from "react-i18next";
import { useStore } from "../../modules/store";
import { SvgButton } from "../SvgButton/SvgButton";
import { t } from "i18next";
import { Icon } from "../Icon/Icon";

interface TranscribeOptionsProps {
  handleSubmit: (
    selectedOption: string,
    youtubeUrl: string,
    audioFile: File | null,
    recordedBlob: Blob | null,
    selectedModel: string
  ) => void;
}

const whisperSizes = ["tiny", "base", "small", "medium", "large-v3"];
const TranscribeOptions: React.FC<TranscribeOptionsProps> = ({
  handleSubmit,
}) => {
  const [youtubeUrl, setYoutubeUrl] = useState<string>("");
  const [audioFile, setAudioFile] = useState<File | null>(null);
  const [recording, setRecording] = useState<boolean>(false);
  const [recordingStarted, setRecordingStarted] = useState<boolean>(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>("small");
  const [selectedOption, setSelectedOption] = useState<string>("youtube");
  const [hoveredButton, setHoveredButton] = useState<string | null>(null);
  const { t } = useTranslation();

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  const startRecording = async () => {
    setRecording(true);
    setRecordingStarted(true);
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
      setRecordingStarted(false);
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
      setRecording(false);
    }
  };

  const resumeRecording = () => {
    if (
      mediaRecorderRef.current &&
      mediaRecorderRef.current.state === "paused"
    ) {
      mediaRecorderRef.current.resume();
      setRecording(true);
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
    <div className="flex-y gap-medium padding-big  rounded justify-center border-gray">
      <div className="flex-x gap-medium ">
        <h4>{t("from")}</h4>
        <button
          className={`button selected ${selectedOption === "youtube" ? "bg-active" : ""}`}
          onClick={() => setSelectedOption("youtube")}
        >
          {t("youtube")}
        </button>
        <button
          className={`button selected ${selectedOption === "microphone" ? "bg-active" : ""}`}
          onClick={() => setSelectedOption("microphone")}
        >
          {t("microphone")}
        </button>
        <button
          className={`button selected ${selectedOption === "audio" ? "bg-active" : ""}`}
          onClick={() => setSelectedOption("audio")}
        >
          {t("audio-file")}
        </button>
      </div>
      {selectedOption === "youtube" && (
        <input
          type="text"
          className="input"
          placeholder={t("enter-youtube-url")}
          value={youtubeUrl}
          onChange={(e) => setYoutubeUrl(e.target.value)}
        />
      )}
      {selectedOption === "microphone" && (
        <div className="flex-x gap-small">
          <SvgButton
            text={recordingStarted ? t("stop-recording") : t("start-recording")}
            size="small"
            extraClass="bg-hovered active-on-hover pressable w-100"
            svg={recordingStarted ? <Icon name="Square" size={20} /> : <Icon name="Play" size={20} />}
            onClick={recordingStarted ? stopRecording : startRecording}
          />
          {recordingStarted && (
            <SvgButton
              text={recording ? t("pause") : t("resume")}
              size="small"
              extraClass="bg-hovered active-on-hover pressable w-100"
              svg={recording ? <Icon name="Pause" size={20} /> : <Icon name="Play" size={20} />}
              onClick={recording ? pauseRecording : resumeRecording}
            />
          )}
        </div>
      )}
      {selectedOption === "audio" && (
        <input
          className="input"
          type="file"
          accept="audio/*,video/*"
          onChange={handleFileChange}
        />
      )}
      {audioUrl && <audio controls src={audioUrl}></audio>}

      {(selectedOption === "microphone" || selectedOption === "audio") && (
        <div className="flex-x gap-small align-center">
          <h4>{t("whisper-size")}</h4>
          <select
            className="input"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
          >
            {whisperSizes.map((size) => (
              <option value={size}>{size}</option>
            ))}
          </select>
        </div>
      )}
      {selectedOption && (
        <button
          className={`px-8 py-3 rounded-full font-normal text-sm cursor-pointer border flex items-center gap-2 w-full justify-center ${
            hoveredButton === 'transcribe' 
              ? 'bg-white text-gray-800 border-[rgba(156,156,156,0.3)]' 
              : 'bg-[rgba(35,33,39,0.5)] text-white border-[rgba(156,156,156,0.3)] hover:bg-[rgba(35,33,39,0.8)]'
          }`}
          style={{ transform: 'none' }}
          onMouseEnter={() => setHoveredButton('transcribe')}
          onMouseLeave={() => setHoveredButton(null)}
          onClick={() => {
            if (selectedOption === "youtube" && !youtubeUrl) {
              toast.error(t("youtube-url-required"));
              return;
            }
            if (selectedOption === "microphone" && !recordedBlob) {
              toast.error(t("you-need-to-record-something-first"));
              return;
            }

            if (selectedOption === "audio" && !audioFile) {
              toast.error(t("you-need-to-upload-an-audio-file-first"));
              return;
            }

            handleSubmit(
              selectedOption,
              youtubeUrl,
              audioFile,
              recordedBlob,
              selectedModel
            );
          }}
          >
          <Icon name="Waves" size={20} />
          <span>{t("transcribe")}</span>
        </button>
      )}
    </div>
  );
};

export const AudioTools: React.FC = () => {
  const { t } = useTranslation();

  const { setOpenedModals } = useStore((state) => ({
    setOpenedModals: state.setOpenedModals,
  }));

  return (
    <Modal
      header={<h4 className="padding-medium">{t("transcribe")}</h4>}
      hide={() => {
        setOpenedModals({ action: "remove", name: "audio" });
      }}
    >
      <Transcriptor />
    </Modal>
  );
};

interface Transcription {
  id: number;
  format: string;
  result: string;
  language: string;
  created_at: string;
}

interface TranscriptionJob {
  id: number;
  status: string;
  source_type: string;
  name: string;
  created_at: string;
  transcriptions: Transcription[];
  status_text: string;
}

const TranscriptionJobCard: React.FC<{
  job: TranscriptionJob;
  handleDelete: (id: number) => void;
}> = ({ job, handleDelete }) => {
  const { t } = useTranslation();

  const downloadResult = (result: string, id: number) => {
    const element = document.createElement("a");
    const file = new Blob([result], { type: "text/plain" });
    element.href = URL.createObjectURL(file);
    element.download = `transcription_${id}.txt`;
    document.body.appendChild(element);
    element.click();
  };

  return (
    <div
      className={`card ${job.status === "PENDING" ? "bg-loading" : job.status === "ERROR" ? "bg-danger" : ""}`}
    >
      <h4 className="flex-x justify-between  gap-small align-center">
        {job.source_type === "AUDIO" ? (
          <p><Icon name="Mic" size={20} /></p>
        ) : (
          <p><Icon name="Youtube" size={20} /></p>
        )}
        <p>{t("transcription")}</p>
        <p>{job.id}</p>
      </h4>

      {job.status === "ERROR" && (
        <div className="text-center">{job.status_text}</div>
      )}
      <div>
        {job.transcriptions.map((transcription) => (
          <div className=" justify-center" key={transcription.id}>
            <SvgButton
              text={`${transcription.language} - ${transcription.format}`}
              size="small"
              extraClass="bg-hovered active-on-hover pressable w-100"
              svg={<Icon name="Download" size={20} />}
              onClick={() =>
                downloadResult(transcription.result, transcription.id)
              }
            />
          </div>
        ))}
      </div>
      {job.status !== "PENDING" ? (
        <div>
          <SvgButton
            text="Delete"
            size="small"
            extraClass="bg-hovered danger-on-hover pressable w-100"
            svg={<Icon name="Trash2" size={20} />}
            confirmations={[t("sure")]}
            onClick={() => handleDelete(job.id)}
          />
        </div>
      ) : (
        <div className="text-center">{t("processing")}</div>
      )}
    </div>
  );
};

const Transcriptor: React.FC = () => {
  const [jobs, setJobs] = useState<TranscriptionJob[]>([]);

  useEffect(() => {
    getTranscriptionJobs();
  }, []);

  useEffect(() => {
    // Ver si hay algun trabajo pendiente
    const pendingJob = jobs.find((job) => job.status === "PENDING");
    if (pendingJob) {
      setTimeout(() => {
        getTranscriptionJobs();
      }, 5000);
    }
  }, [jobs]);

  const getTranscriptionJobs = async () => {
    const data = await makeAuthenticatedRequest<TranscriptionJob[]>(
      "GET",
      "/v1/tools/transcriptions/"
    );
    setJobs(data);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteTranscriptionJob(id);

      toast.success("Transcription job deleted");
      await getTranscriptionJobs();
    } catch (error) {
      console.error("Error:", error);
      toast.error("Something failed in the server 👀");
    }
  };

  const handleSubmit = async (
    selectedOption: string,
    youtubeUrl: string,
    audioFile: File | null,
    recordedBlob: Blob | null,
    selectedModel: string
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

    formData.append("whisper_size", selectedModel);

    try {
      const responseData = await makeAuthenticatedRequest(
        "POST",
        `/v1/tools/transcriptions/`,
        formData
      );

      console.log(responseData);
      toast.success(t("transcription-job-initialized"));

      setTimeout(() => {
        getTranscriptionJobs();
      }, 2000);
    } catch (error) {
      console.error("Error:", error);
      toast.error("Something failed in the server 👀");
    }
  };

  return (
    <div className="">
      <TranscribeOptions handleSubmit={handleSubmit} />

      <div className="wrap-wrap padding-medium flex-x gap-medium">
        {jobs.map((job) => (
          <TranscriptionJobCard
            key={job.id}
            job={job}
            handleDelete={handleDelete}
          />
        ))}
      </div>
    </div>
  );
};
