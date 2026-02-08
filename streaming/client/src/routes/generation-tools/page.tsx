import React, { useState, useRef, useEffect } from "react";
import { useStore } from "../../modules/store";
import { Sidebar } from "../../components/Sidebar/Sidebar";
import {
  deleteTranscriptionJob,
  makeAuthenticatedRequest,
} from "../../modules/apiCalls";
import toast from "react-hot-toast";
import { useTranslation } from "react-i18next";

import {
  ActionIcon,
  Badge,
  Box,
  Button,
  Card,
  CopyButton,
  FileInput,
  Group,
  Loader,
  Modal,
  ScrollArea,
  SegmentedControl,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import {
  IconCheck,
  IconCopy,
  IconDownload,
  IconEye,
  IconMenu2,
  IconMicrophone,
  IconPlayerPause,
  IconPlayerPlay,
  IconPlayerStop,
  IconTrash,
  IconUpload,
  IconWaveSine,
} from "@tabler/icons-react";

// ─── Types ────────────────────────────────────────────────────────────────────

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

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function GenerationToolsPage() {
  const { chatState, toggleSidebar } = useStore((s) => ({
    chatState: s.chatState,
    toggleSidebar: s.toggleSidebar,
  }));

  const { t } = useTranslation();

  return (
    <main className="d-flex pos-relative h-viewport">
      {chatState.isSidebarOpened && <Sidebar />}
      <div
        style={{
          flex: "1 1 auto",
          minWidth: 0,
          padding: 24,
          overflowY: "auto",
          minHeight: "100vh",
          display: "flex",
          justifyContent: "center",
        }}
        className="relative"
      >
        {!chatState.isSidebarOpened && (
          <Box pos="absolute" top={24} left={24} style={{ zIndex: 10 }}>
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={toggleSidebar}
            >
              <IconMenu2 size={20} />
            </ActionIcon>
          </Box>
        )}

        <Box px="md" w="100%" maw="52rem" mx="auto">
          <Title order={2} ta="center" mb="lg" mt="md">
            {t("audio-tools")}
          </Title>

          <Stack gap="lg">
            <TranscriptionSection />
          </Stack>
        </Box>
      </div>
    </main>
  );
}

// ─── Transcription Section ────────────────────────────────────────────────────

const TranscriptionSection = () => {
  const { t } = useTranslation();
  const [jobs, setJobs] = useState<TranscriptionJob[]>([]);
  const [loading, setLoading] = useState(false);

  // Source options
  const [sourceType, setSourceType] = useState("youtube");
  const [youtubeUrl, setYoutubeUrl] = useState("");
  const [audioFile, setAudioFile] = useState<File | null>(null);

  // Recording
  const [recording, setRecording] = useState(false);
  const [recordingStarted, setRecordingStarted] = useState(false);
  const [recordedBlob, setRecordedBlob] = useState<Blob | null>(null);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    const pendingJob = jobs.find((job) => job.status === "PENDING");
    if (pendingJob) {
      const timer = setTimeout(fetchJobs, 5000);
      return () => clearTimeout(timer);
    }
  }, [jobs]);

  const fetchJobs = async () => {
    try {
      const data = await makeAuthenticatedRequest<TranscriptionJob[]>(
        "GET",
        "/v1/tools/transcriptions/"
      );
      setJobs(data);
    } catch {
      console.error("Failed to fetch transcription jobs");
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteTranscriptionJob(id);
      toast.success(t("transcription-deleted"));
      await fetchJobs();
    } catch {
      toast.error(t("an-error-occurred"));
    }
  };

  // ── Recording controls ──

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
    mediaRecorderRef.current?.stop();
  };

  const pauseRecording = () => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.pause();
      setRecording(false);
    }
  };

  const resumeRecording = () => {
    if (mediaRecorderRef.current?.state === "paused") {
      mediaRecorderRef.current.resume();
      setRecording(true);
    }
  };

  // ── Submit ──

  const handleSubmit = async () => {
    if (sourceType === "youtube" && !youtubeUrl) {
      toast.error(t("youtube-url-required"));
      return;
    }
    if (sourceType === "microphone" && !recordedBlob) {
      toast.error(t("you-need-to-record-something-first"));
      return;
    }
    if (sourceType === "audio" && !audioFile) {
      toast.error(t("you-need-to-upload-an-audio-file-first"));
      return;
    }

    setLoading(true);
    const formData = new FormData();

    if (sourceType === "youtube") {
      formData.append("source", "youtube_url");
      formData.append("youtube_url", youtubeUrl);
    } else if (sourceType === "audio" && audioFile) {
      const fileType = audioFile.type.startsWith("video/") ? "video" : "audio";
      formData.append("source", fileType);
      formData.append(`${fileType}_file`, audioFile);
    } else if (sourceType === "microphone" && recordedBlob) {
      formData.append("source", "audio");
      formData.append("audio_file", recordedBlob, "recording.wav");
    }

    try {
      await makeAuthenticatedRequest(
        "POST",
        "/v1/tools/transcriptions/",
        formData
      );
      toast.success(t("transcription-job-initialized"));
      setTimeout(fetchJobs, 2000);
    } catch {
      toast.error(t("an-error-occurred"));
    } finally {
      setLoading(false);
    }
  };

  // ── Render ──

  return (
    <>
      {/* ── New transcription ── */}
      <Card withBorder p="lg">
        <Title order={4} mb="md">
          {t("transcribe")}
        </Title>

        <Stack gap="md">
          <SegmentedControl
            value={sourceType}
            onChange={setSourceType}
            data={[
              { label: t("youtube"), value: "youtube" },
              { label: t("microphone"), value: "microphone" },
              { label: t("audio-file"), value: "audio" },
            ]}
            fullWidth
          />

          {sourceType === "youtube" && (
            <TextInput
              placeholder={t("enter-youtube-url")}
              value={youtubeUrl}
              onChange={(e) => setYoutubeUrl(e.currentTarget.value)}
            />
          )}

          {sourceType === "microphone" && (
            <Stack gap="sm">
              <Group gap="xs">
                <Button
                  variant="default"
                  leftSection={
                    recordingStarted ? (
                      <IconPlayerStop size={16} />
                    ) : (
                      <IconMicrophone size={16} />
                    )
                  }
                  onClick={recordingStarted ? stopRecording : startRecording}
                >
                  {recordingStarted
                    ? t("stop-recording")
                    : t("start-recording")}
                </Button>
                {recordingStarted && (
                  <Button
                    variant="default"
                    leftSection={
                      recording ? (
                        <IconPlayerPause size={16} />
                      ) : (
                        <IconPlayerPlay size={16} />
                      )
                    }
                    onClick={recording ? pauseRecording : resumeRecording}
                  >
                    {recording ? t("pause") : t("resume")}
                  </Button>
                )}
              </Group>
            </Stack>
          )}

          {sourceType === "audio" && (
            <FileInput
              placeholder={t("upload-audio-file")}
              accept="audio/*,video/*"
              value={audioFile}
              onChange={setAudioFile}
              leftSection={<IconUpload size={16} />}
            />
          )}

          {audioUrl && (
            <audio controls src={audioUrl} style={{ width: "100%" }} />
          )}

          <Button
            leftSection={<IconWaveSine size={16} />}
            onClick={handleSubmit}
            loading={loading}
          >
            {t("transcribe")}
          </Button>
        </Stack>
      </Card>

      {/* ── Jobs list ── */}
      {jobs.length > 0 && (
        <Card withBorder p="lg">
          <Title order={4} mb="md">
            {t("transcription-jobs")}
          </Title>

          <Stack gap="sm">
            {jobs.map((job) => (
              <TranscriptionJobCard
                key={job.id}
                job={job}
                onDelete={handleDelete}
              />
            ))}
          </Stack>
        </Card>
      )}
    </>
  );
};

// ─── Job Card ─────────────────────────────────────────────────────────────────

const TranscriptionJobCard = ({
  job,
  onDelete,
}: {
  job: TranscriptionJob;
  onDelete: (id: number) => void;
}) => {
  const { t } = useTranslation();
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [previewContent, setPreviewContent] = useState<{
    result: string;
    label: string;
  } | null>(null);

  const downloadResult = (result: string, id: number) => {
    const blob = new Blob([result], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `transcription_${id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const isPending = job.status === "PENDING";
  const isError = job.status === "ERROR";

  return (
    <>
      {/* Preview modal */}
      <Modal
        opened={previewContent !== null}
        onClose={() => setPreviewContent(null)}
        title={previewContent?.label}
        size="lg"
      >
        {previewContent && (
          <Stack gap="sm">
            <Group gap="xs" justify="flex-end">
              <CopyButton value={previewContent.result}>
                {({ copied, copy }) => (
                  <Tooltip label={copied ? t("copied") : t("copy")}>
                    <ActionIcon
                      variant="default"
                      onClick={copy}
                      color={copied ? "teal" : undefined}
                    >
                      {copied ? <IconCheck size={16} /> : <IconCopy size={16} />}
                    </ActionIcon>
                  </Tooltip>
                )}
              </CopyButton>
              <Tooltip label={t("download")}>
                <ActionIcon
                  variant="default"
                  onClick={() =>
                    downloadResult(previewContent.result, job.id)
                  }
                >
                  <IconDownload size={16} />
                </ActionIcon>
              </Tooltip>
            </Group>
            <ScrollArea.Autosize mah="60vh">
              <Text
                size="sm"
                style={{ whiteSpace: "pre-wrap", fontFamily: "monospace" }}
              >
                {previewContent.result}
              </Text>
            </ScrollArea.Autosize>
          </Stack>
        )}
      </Modal>

      <Card
        withBorder
        p="sm"
        style={{
          background: isError
            ? "rgba(255,0,0,0.05)"
            : isPending
              ? "rgba(255,255,255,0.03)"
              : "rgba(255,255,255,0.02)",
        }}
      >
        <Group justify="space-between" wrap="nowrap" mb="xs">
          <Group gap="xs" style={{ overflow: "hidden", flex: 1 }}>
            <Badge
              variant="default"
              size="sm"
              leftSection={
                job.source_type === "AUDIO" ? (
                  <IconMicrophone size={12} />
                ) : (
                  <IconWaveSine size={12} />
                )
              }
            >
              #{job.id}
            </Badge>
            {job.name && (
              <Text size="sm" c="dimmed" truncate style={{ flex: 1 }}>
                {job.name}
              </Text>
            )}
            {isPending && <Loader size="xs" color="violet" />}
            {isError && (
              <Badge color="red" size="sm">
                {t("error")}
              </Badge>
            )}
          </Group>

          {!isPending && (
            <Button
              variant="light"
              color={confirmDelete ? "red" : "gray"}
              size="xs"
              leftSection={<IconTrash size={14} />}
              onClick={() => {
                if (confirmDelete) {
                  onDelete(job.id);
                  setConfirmDelete(false);
                } else {
                  setConfirmDelete(true);
                }
              }}
              onBlur={() => setConfirmDelete(false)}
            >
              {confirmDelete ? t("im-sure") : t("delete")}
            </Button>
          )}
        </Group>

        {isError && (
          <Text size="sm" c="red" mb="xs">
            {job.status_text}
          </Text>
        )}

        {isPending && (
          <Text size="sm" c="dimmed">
            {t("processing")}
          </Text>
        )}

        {job.transcriptions.length > 0 && (
          <Stack gap={4}>
            {job.transcriptions.map((tr) => (
              <Group key={tr.id} gap={4} wrap="nowrap">
                <Button
                  variant="default"
                  size="xs"
                  leftSection={<IconEye size={14} />}
                  onClick={() =>
                    setPreviewContent({
                      result: tr.result,
                      label: `${tr.language} — ${tr.format}`,
                    })
                  }
                  style={{ flex: 1 }}
                >
                  {tr.language} — {tr.format}
                </Button>
                <Tooltip label={t("download")}>
                  <ActionIcon
                    variant="default"
                    size="sm"
                    onClick={() => downloadResult(tr.result, tr.id)}
                  >
                    <IconDownload size={14} />
                  </ActionIcon>
                </Tooltip>
              </Group>
            ))}
          </Stack>
        )}
      </Card>
    </>
  );
};
