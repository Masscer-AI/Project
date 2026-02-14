import React, { useEffect, useRef, useState } from "react";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { AttatchmentMode } from "../../types";
import toast from "react-hot-toast";
import { generateVideo } from "../../modules/apiCalls";
import { AspectRatio } from "../ImageGenerator/ImageGenerator";
import { API_URL } from "../../modules/constants";
import {
  Menu,
  Modal,
  Switch,
  Button,
  ActionIcon,
  Stack,
  Text,
  Textarea,
  NativeSelect,
  Group,
  Tooltip,
} from "@mantine/core";
import {
  IconDotsVertical,
  IconTrash,
  IconFileText,
  IconDownload,
  IconVideo,
  IconX,
  IconCheck,
  IconPlayerPlay,
} from "@tabler/icons-react";

interface ThumbnailProps {
  id?: number | string;
  src: string;
  type: string;
  content: string;
  name: string;
  index: number;
  text?: string;
  showFloatingButtons?: boolean;
  mode?: AttatchmentMode;
  message_id?: number;
}

export const Thumbnail = ({
  id,
  src,
  text,
  content,
  type,
  name,
  index,
  showFloatingButtons = false,
  mode,
  message_id,
}: ThumbnailProps) => {
  const { t } = useTranslation();
  const { deleteAttachment } = useStore((state) => ({
    deleteAttachment: state.deleteAttachment,
  }));

  return (
    <>
      {type.indexOf("audio") !== 0 &&
        type.indexOf("image") !== 0 &&
        type.indexOf("video_generation") !== 0 &&
        type.indexOf("audio_generation") !== 0 && (
          <DocumentThumnail
            id={id}
            index={index}
            onDelete={() => deleteAttachment(index)}
            // type={type}

            name={name}
            showFloatingButtons={showFloatingButtons}
            mode={mode}
          />
        )}
      {type.indexOf("image") === 0 && (
        <div className="thumbnail pointer flex-shrink-0">
          <ImageThumbnail
            src={src}
            message_id={message_id}
            name={name}
            buttons={
              showFloatingButtons && (
                <div className="d-flex align-center justify-center padding-small">
                  <ActionIcon
                    variant="subtle"
                    color="red"
                    size="sm"
                    onClick={() => deleteAttachment(index)}
                    title={t("delete")}
                  >
                    <IconTrash size={16} />
                  </ActionIcon>
                </div>
              )
            }
          />
        </div>
      )}
      {/* Audio type currently unused */}
      {type.indexOf("audio_generation") === 0 && (
        <AudioThumbnail src={content} />
      )}

      {type.indexOf("video_generation") === 0 && (
        <>
          <VideoThumbnail id={id} src={src} text={text} />

        </>
      )}
    </>
  );
};

const aspectRatioOptions = [
  { label: "1280:768", value: "1280:768" },
  { label: "768:1280", value: "768:1280" },
];

const ImageModal = ({
  src,
  name,
  hide,
  message_id,
}: {
  src: string;
  name: string;
  hide: () => void;
  message_id?: number;
}) => {
  const [showGenerationOptions, setShowGenerationOptions] = useState(false);
  const { t } = useTranslation();
  const [videoPrompt, setVideoPrompt] = useState("");
  const [ratio, setRatio] = useState("768:1280");

  const handleDownload = () => {
    const a = document.createElement("a");
    const isDataOrUrl =
      src.startsWith("data:") || src.startsWith("http") || src.startsWith("/");
    a.href = isDataOrUrl ? src : `data:image/png;base64,${src}`;
    a.setAttribute("download", name);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  const toggleGenerateVideo = () => {
    setShowGenerationOptions(!showGenerationOptions);
  };

  const handleGenerateVideo = async () => {
    await generateVideo({
      prompt: videoPrompt,
      image_b64: src,
      message_id: message_id!,
      ratio: ratio,
    });

    toast.success(t("video-job-started"));
    setShowGenerationOptions(false);
  };

  const canGenerateVideo = message_id != null;

  return (
    <Modal
      opened={true}
      onClose={hide}
      title={
        <Group justify="space-between" wrap="nowrap" style={{ width: "100%" }}>
          <Text fw={600} size="lg">
            {showGenerationOptions ? t("generate-video") : t("image-preview")}
          </Text>
          <Group gap="xs" align="center">
            <Tooltip label={t("download")} withArrow>
              <ActionIcon
                variant="subtle"
                color="gray"
                size="md"
                onClick={handleDownload}
              >
                <IconDownload size={18} />
              </ActionIcon>
            </Tooltip>
            {canGenerateVideo && (
              <Tooltip
                label={
                  showGenerationOptions ? t("cancel") : t("generate-video")
                }
                withArrow
              >
                <ActionIcon
                  variant="light"
                  color="violet"
                  size="md"
                  onClick={toggleGenerateVideo}
                >
                  {showGenerationOptions ? (
                    <IconX size={18} />
                  ) : (
                    <IconVideo size={18} />
                  )}
                </ActionIcon>
              </Tooltip>
            )}
          </Group>
        </Group>
      }
      size="lg"
      centered
      padding="md"
      styles={{
        header: { paddingBottom: 12 },
        body: { paddingTop: 8 },
      }}
    >
      {showGenerationOptions ? (
        <Stack gap="sm" w="100%" align="center">
          <Group gap="sm" justify="center">
            <Text size="sm" fw={500}>
              {t("aspect-ratio")}
            </Text>
            {aspectRatioOptions.map((option) => (
              <AspectRatio
                key={option.value}
                size={option.value}
                separator=":"
                selected={ratio === option.value}
                onClick={() => setRatio(option.value)}
              />
            ))}
          </Group>
          <Textarea
            label={t("describe-the-video")}
            value={videoPrompt}
            onChange={(e) => setVideoPrompt(e.currentTarget.value)}
            maxLength={512}
            w="100%"
            autosize
            minRows={2}
          />
          <img
            style={{ width: "40%", maxHeight: "40vh", objectFit: "contain" }}
            src={src}
            alt={`attachment-${name}`}
          />
          <Button
            fullWidth
            leftSection={<IconCheck size={16} />}
            onClick={handleGenerateVideo}
          >
            {t("generate-video")}
          </Button>
        </Stack>
      ) : (
        <div
          style={{
            display: "flex",
            justifyContent: "center",
            alignItems: "center",
            maxHeight: "calc(100vh - 140px)",
            overflow: "auto",
          }}
        >
          <img
            style={{
              maxWidth: "100%",
              maxHeight: "calc(100vh - 160px)",
              objectFit: "contain",
            }}
            src={src}
            alt={`attachment-${name}`}
          />
        </div>
      )}
    </Modal>
  );
};

const DocumentThumnail = ({
  index,
  name,
  onDelete,
  id,
  showFloatingButtons,
  mode,
}: {
  index: number;
  name: string;
  onDelete: () => void;
  id?: number | string;
  showFloatingButtons: boolean;
  mode?: AttatchmentMode;
}) => {
  const { updateAttachment } = useStore((state) => ({
    updateAttachment: state.updateAttachment,
  }));
  const { t } = useTranslation();
  const [ragMode, setRagMode] = useState<AttatchmentMode>(
    mode ? mode : "similar_chunks"
  );
  const [confirmDelete, setConfirmDelete] = useState(false);

  const ragModeHelpHelper: Record<string, string> = {
    similar_chunks: t("chunks-mode-help-text"),
    all_possible_text: t("all-content-mode-help-text"),
  };

  useEffect(() => {
    updateAttachment(index, { mode: ragMode });
  }, [ragMode]);

  return (
    <div
      title={name}
      className="width-150 document-attachment bg-contrast rounded padding-small"
    >
      <div className="d-flex gap-small align-center">
        <div>
          <IconFileText size={20} />
        </div>
        <p className="cut-text-to-line">{name}</p>

        {showFloatingButtons && (
          <Menu
            shadow="md"
            width={240}
            position="top"
            withArrow
            closeOnItemClick={false}
          >
            <Menu.Target>
              <ActionIcon variant="subtle" color="gray" size="sm">
                <IconDotsVertical size={16} />
              </ActionIcon>
            </Menu.Target>
            <Menu.Dropdown>
              <Stack gap="sm" p="xs">
                <Text fw={500} ta="center" size="sm">
                  {t("configure")}
                </Text>
                <Switch
                  label={
                    ragMode === "similar_chunks"
                      ? t("similar-chunks")
                      : t("allContent")
                  }
                  checked={ragMode === "similar_chunks"}
                  onChange={(e) => {
                    setRagMode(
                      e.currentTarget.checked
                        ? "similar_chunks"
                        : "all_possible_text"
                    );
                  }}
                  color="violet"
                />
                <MarkdownRenderer
                  extraClass="text-mini"
                  markdown={ragModeHelpHelper[ragMode]}
                />
                <Button
                  color={confirmDelete ? "red" : "red"}
                  variant={confirmDelete ? "filled" : "light"}
                  leftSection={<IconTrash size={16} />}
                  fullWidth
                  onClick={() => {
                    if (!confirmDelete) {
                      setConfirmDelete(true);
                      return;
                    }
                    onDelete();
                    setConfirmDelete(false);
                  }}
                  onMouseLeave={() => setConfirmDelete(false)}
                >
                  {confirmDelete ? t("sure") : t("delete")}
                </Button>
              </Stack>
            </Menu.Dropdown>
          </Menu>
        )}
      </div>
    </div>
  );
};

const ImageThumbnail = ({
  src,
  name,
  buttons,
  message_id,
}: {
  src: string;
  name: string;
  buttons?: React.ReactNode;
  message_id?: number;
}) => {
  const [showModal, setShowModal] = useState(false);

  return (
    <div className="thumbnail pointer flex-shrink-0">
      {showModal && (
        <ImageModal
          src={src}
          name={name}
          hide={() => setShowModal(false)}
          message_id={message_id}
        />
      )}
      <img
        onClick={() => setShowModal(true)}
        src={src}
        alt={`attachment-${name}`}
        className="max-w-[70px] max-h-[70px] w-[70px] h-[70px] object-contain rounded-md flex-shrink-0"
      />
      {buttons}
    </div>
  );
};

const VideoThumbnail = ({
  id,
  src,
  text,
}: {
  id?: string | number;
  src: string;
  text?: string;
  // name: string;
}) => {
  id;
  const [openModal, setOpenModal] = useState(false);

  return (
    <div className="thumbnail pointer">
      {openModal && (
        <VideoModal
          url={API_URL + src}
          close={() => setOpenModal(false)}
          text={text}
        />
      )}
      <ActionIcon variant="subtle" color="gray" onClick={() => setOpenModal(true)} title="Open">
        <IconPlayerPlay size={20} />
      </ActionIcon>
    </div>
  );
};

const VideoModal = ({
  url,
  close,
  text,
}: {
  url: string;
  close: () => void;
  text?: string;
}) => {
  const { t } = useTranslation();

  const download = () => {
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", "video.mp4");
    a.setAttribute("target", "_blank");
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <Modal opened={true} onClose={close} title={t("generated-video")} size="lg" centered>
      <Stack gap="md">
        <ActionIcon variant="default" onClick={download} title={t("download")}>
          <IconDownload size={18} />
        </ActionIcon>
        <Text size="sm">
          <strong>Prompt: </strong>
          {text}
        </Text>
        <video style={{ width: "100%" }} src={url} autoPlay controls />
      </Stack>
    </Modal>
  );
};

const AudioThumbnail = ({ src }: { src: string }) => {
  const audioRef = useRef<HTMLAudioElement>(null);

  return (
    <div className="">
      <audio ref={audioRef} controls src={API_URL + src} playsInline />
    </div>
  );
};
