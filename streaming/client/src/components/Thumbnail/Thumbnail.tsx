import React, { useRef, useState } from "react";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { AttatchmentMode } from "../../types";
import { API_URL } from "../../modules/constants";
import {
  Modal,
  ActionIcon,
  Stack,
  Text,
  Group,
  Tooltip,
} from "@mantine/core";
import {
  IconTrash,
  IconFileText,
  IconDownload,
  IconX,
  IconLink,
} from "@tabler/icons-react";

const VIDEO_EXT_RE = /\.(mp4|webm|mov|m4v|ogv)(\?|#|$)/i;

/** True for video/* MIME, legacy video_generation, or obvious video filenames (e.g. mis-typed as document). */
function isVideoAttachmentType(type: string, name: string, content: string): boolean {
  const t = type || "";
  if (t.startsWith("video/") || t.startsWith("video_generation")) return true;
  if (t.startsWith("image") || t.startsWith("audio")) return false;
  return VIDEO_EXT_RE.test(name || "") || VIDEO_EXT_RE.test(content || "");
}

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
}: ThumbnailProps) => {
  const { t } = useTranslation();
  const { deleteAttachment } = useStore((state) => ({
    deleteAttachment: state.deleteAttachment,
  }));

  return (
    <>
      {type === "website" && (
        <WebsiteThumbnail
          url={src || content}
          name={name}
        />
      )}
      {type.indexOf("audio") !== 0 &&
        type.indexOf("image") !== 0 &&
        !isVideoAttachmentType(type, name, content) &&
        type.indexOf("audio_generation") !== 0 && (
          type !== "website" && (
          <DocumentThumnail
            id={id}
            index={index}
            onDelete={() => deleteAttachment(index)}
            name={name}
            src={src}
            showFloatingButtons={showFloatingButtons}
            mode={mode}
          />
          )
        )}
      {type.indexOf("image") === 0 && (
        <ImageAttachmentThumbnail
          src={src}
          name={name}
          showFloatingButtons={showFloatingButtons}
          onDelete={() => deleteAttachment(index)}
        />
      )}
      {/* Audio type currently unused */}
      {type.indexOf("audio_generation") === 0 && (
        <AudioThumbnail src={content} />
      )}

      {isVideoAttachmentType(type, name, content) && (
        <VideoAttachmentThumbnail
          src={src}
          name={name}
          text={text}
          showFloatingButtons={showFloatingButtons}
          onDelete={() => deleteAttachment(index)}
        />
      )}
    </>
  );
};

const ImageAttachmentThumbnail = ({
  src,
  name,
  showFloatingButtons,
  onDelete,
}: {
  src: string;
  name: string;
  showFloatingButtons: boolean;
  onDelete: () => void;
}) => {
  const { t } = useTranslation();
  const [showModal, setShowModal] = useState(false);

  if (!showFloatingButtons) {
    // In-message rendering (compact square preview)
    return (
      <div className="thumbnail pointer flex-shrink-0">
        {showModal && (
          <ImageModal src={src} name={name} hide={() => setShowModal(false)} />
        )}
        <img
          onClick={() => setShowModal(true)}
          src={src}
          alt={`attachment-${name}`}
          className="max-w-[70px] max-h-[70px] w-[70px] h-[70px] object-contain rounded-md flex-shrink-0"
        />
      </div>
    );
  }

  // Input strip rendering (match document/website chips)
  return (
    <div className="width-150 document-attachment bg-contrast rounded padding-small">
      {showModal && (
        <ImageModal src={src} name={name} hide={() => setShowModal(false)} />
      )}
      <div className="d-flex gap-small align-center">
        <img
          onClick={() => setShowModal(true)}
          src={src}
          alt={`attachment-${name}`}
          className="w-[38px] h-[38px] object-cover rounded-md flex-shrink-0 pointer"
        />
        <p
          className="cut-text-to-line"
          style={{ flex: 1, minWidth: 0, margin: 0 }}
        >
          {name}
        </p>
        <ActionIcon
          variant="subtle"
          color="red"
          size="sm"
          onClick={onDelete}
          title={t("delete")}
          aria-label={t("delete")}
        >
          <IconTrash size={16} />
        </ActionIcon>
      </div>
    </div>
  );
};

const WebsiteThumbnail = ({ url, name }: { url: string; name: string }) => {
  const safeUrl = url || "";
  const display = name || safeUrl;

  return (
    <a
      href={safeUrl}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={safeUrl}
      className="width-150 document-attachment bg-contrast rounded padding-small"
      style={{
        display: "flex",
        gap: 8,
        alignItems: "center",
        textDecoration: "none",
        color: "inherit",
      }}
    >
      <IconLink size={20} />
      <p className="cut-text-to-line" style={{ flex: 1, margin: 0 }}>
        {display}
      </p>
    </a>
  );
};

const ImageModal = ({
  src,
  name,
  hide,
}: {
  src: string;
  name: string;
  hide: () => void;
}) => {
  const { t } = useTranslation();

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

  return (
    <Modal
      opened={true}
      onClose={hide}
      title={
        <Group justify="space-between" wrap="nowrap" style={{ width: "100%" }}>
          <Text fw={600} size="lg">
            {t("image-preview")}
          </Text>
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
    </Modal>
  );
};

const DocumentThumnail = ({
  index,
  name,
  src,
  onDelete,
  id,
  showFloatingButtons,
  mode,
}: {
  index: number;
  name: string;
  src: string;
  onDelete: () => void;
  id?: number | string;
  showFloatingButtons: boolean;
  mode?: AttatchmentMode;
}) => {
  const cardContent = (
    <div className="d-flex gap-small align-center">
      <div>
        <IconFileText size={20} />
      </div>
      <p className="cut-text-to-line" style={{ margin: 0, flex: 1, minWidth: 0 }}>
        {name}
      </p>
      {!showFloatingButtons && <IconDownload size={16} />}

      {showFloatingButtons && (
        <ActionIcon
          variant="subtle"
          color="red"
          size="sm"
          onClick={onDelete}
        >
          <IconX size={16} />
        </ActionIcon>
      )}
    </div>
  );

  if (!showFloatingButtons && src) {
    return (
      <a
        href={src}
        download={name || "document"}
        target="_blank"
        rel="noopener noreferrer"
        title={name}
        className="width-150 document-attachment bg-contrast rounded padding-small"
        style={{ textDecoration: "none", color: "inherit", display: "block" }}
      >
        {cardContent}
      </a>
    );
  }

  return (
    <div
      title={name}
      className="width-150 document-attachment bg-contrast rounded padding-small"
    >
      {cardContent}
    </div>
  );
};

const resolveVideoUrl = (src: string) => {
  if (!src) return src;
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) return src;
  return `${API_URL}${src.startsWith("/") ? "" : "/"}${src}`;
};

const VideoAttachmentThumbnail = ({
  src,
  name,
  text,
  showFloatingButtons,
  onDelete,
}: {
  src: string;
  name: string;
  text?: string;
  showFloatingButtons: boolean;
  onDelete: () => void;
}) => {
  const { t } = useTranslation();
  const [showModal, setShowModal] = useState(false);
  const videoUrl = resolveVideoUrl(src);

  const preview = (
    <video
      src={videoUrl}
      muted
      playsInline
      preload="metadata"
      tabIndex={0}
      aria-label={name}
      onClick={() => setShowModal(true)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          setShowModal(true);
        }
      }}
      className="rounded-md flex-shrink-0 pointer bg-black/40"
      style={{
        objectFit: "cover",
        maxWidth: showFloatingButtons ? 38 : 70,
        maxHeight: showFloatingButtons ? 38 : 70,
        width: showFloatingButtons ? 38 : 70,
        height: showFloatingButtons ? 38 : 70,
      }}
    />
  );

  if (!showFloatingButtons) {
    return (
      <div className="thumbnail pointer flex-shrink-0">
        {showModal && (
          <VideoModal url={videoUrl} name={name} close={() => setShowModal(false)} text={text} />
        )}
        {preview}
      </div>
    );
  }

  return (
    <div className="width-150 document-attachment bg-contrast rounded padding-small">
      {showModal && (
        <VideoModal url={videoUrl} name={name} close={() => setShowModal(false)} text={text} />
      )}
      <div className="d-flex gap-small align-center">
        {preview}
        <p
          className="cut-text-to-line"
          style={{ flex: 1, minWidth: 0, margin: 0 }}
        >
          {name}
        </p>
        <ActionIcon
          variant="subtle"
          color="red"
          size="sm"
          onClick={onDelete}
          title={t("delete")}
          aria-label={t("delete")}
        >
          <IconTrash size={16} />
        </ActionIcon>
      </div>
    </div>
  );
};

const VideoModal = ({
  url,
  name,
  close,
  text,
}: {
  url: string;
  name: string;
  close: () => void;
  text?: string;
}) => {
  const { t } = useTranslation();

  const download = () => {
    const a = document.createElement("a");
    a.href = url;
    a.setAttribute("download", name || "video.mp4");
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  };

  return (
    <Modal
      opened={true}
      onClose={close}
      title={
        <Group justify="space-between" wrap="nowrap" style={{ width: "100%" }}>
          <Text fw={600} size="lg">
            {t("generated-video")}
          </Text>
          <Tooltip label={t("download")} withArrow>
            <ActionIcon variant="subtle" color="gray" size="md" onClick={download}>
              <IconDownload size={18} />
            </ActionIcon>
          </Tooltip>
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
      <Stack gap="md">
        {text ? (
          <Text size="sm">
            <strong>{t("prompt")}: </strong>
            {text}
          </Text>
        ) : null}
        <video
          style={{ width: "100%", maxHeight: "calc(100vh - 200px)", borderRadius: 8 }}
          src={url}
          autoPlay
          controls
          playsInline
        />
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
