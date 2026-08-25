import React, { useState } from "react";
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
  UnstyledButton,
} from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import {
  IconTrash,
  IconDownload,
  IconX,
  IconLink,
  IconMusic,
  IconSignature,
  IconCircleCheck,
} from "@tabler/icons-react";
import { AttachmentDetailsModal } from "../AttachmentVisibility/AttachmentVisibilityModal";
import { DocumentFileIcon } from "../../modules/documentFileMeta";
import type { TGalleryItem } from "../../modules/apiCalls";

const VIDEO_EXT_RE = /\.(mp4|webm|mov|m4v|ogv)(\?|#|$)/i;

function isVideoAttachmentType(type: string, name: string, content: string): boolean {
  const t = type || "";
  if (t.startsWith("video/") || t.startsWith("video_generation")) return true;
  if (t.startsWith("image") || t.startsWith("audio")) return false;
  return VIDEO_EXT_RE.test(name || "") || VIDEO_EXT_RE.test(content || "");
}

function isAudioAttachmentType(type: string): boolean {
  const t = type || "";
  return t.indexOf("audio") === 0;
}

function resolveAttachmentFileId(
  attachmentId?: string,
  id?: number | string
): string | undefined {
  if (attachmentId) return String(attachmentId);
  if (typeof id === "string" && id.includes("-")) return id;
  return undefined;
}

function detailsInitialItem(opts: {
  fileId?: string;
  src: string;
  name: string;
  visibility?: "personal" | "organization" | "roles" | "link";
  type: TGalleryItem["type"];
  contentType?: string;
}): TGalleryItem | null {
  if (!opts.fileId) return null;
  return {
    id: opts.fileId,
    url: opts.src,
    content_type: opts.contentType || "",
    type: opts.type,
    name: opts.name,
    prompt: null,
    metadata: {},
    conversation_id: "",
    conversation_title: "",
    message_id: null,
    created_at: null,
    visibility: opts.visibility || "personal",
  };
}

interface ThumbnailProps {
  id?: number | string;
  attachment_id?: string;
  visibility?: "personal" | "organization" | "roles" | "link";
  src: string;
  type: string;
  content: string;
  name: string;
  index: number;
  text?: string;
  showFloatingButtons?: boolean;
  mode?: AttatchmentMode;
  status?: string;
  signatory_name?: string;
}

export const Thumbnail = ({
  id,
  attachment_id,
  visibility,
  src,
  text,
  content,
  type,
  name,
  index,
  showFloatingButtons = false,
  mode,
  status,
  signatory_name,
}: ThumbnailProps) => {
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
      {type === "signature_request" && (
        <SignatureRequestThumbnail
          url={src || content}
          name={name}
          status={status}
          signatoryName={signatory_name}
        />
      )}
      {type.indexOf("audio") !== 0 &&
        type.indexOf("image") !== 0 &&
        !isVideoAttachmentType(type, name, content) &&
        type !== "website" &&
        type !== "signature_request" && (
          <DocumentThumnail
            id={id}
            attachmentId={attachment_id}
            visibility={visibility}
            index={index}
            onDelete={() => deleteAttachment(index)}
            name={name}
            src={src}
            showFloatingButtons={showFloatingButtons}
          />
        )}
      {type.indexOf("image") === 0 && (
        <ImageAttachmentThumbnail
          id={id}
          attachmentId={attachment_id}
          visibility={visibility}
          src={src}
          name={name}
          showFloatingButtons={showFloatingButtons}
          onDelete={() => deleteAttachment(index)}
        />
      )}
      {isAudioAttachmentType(type) && (
        <AudioThumbnail
          id={id}
          attachmentId={attachment_id}
          visibility={visibility}
          src={content || src}
          name={name}
          showFloatingButtons={showFloatingButtons}
          onDelete={() => deleteAttachment(index)}
        />
      )}

      {isVideoAttachmentType(type, name, content) && (
        <VideoAttachmentThumbnail
          id={id}
          attachmentId={attachment_id}
          visibility={visibility}
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
  id,
  attachmentId,
  visibility,
  src,
  name,
  showFloatingButtons,
  onDelete,
}: {
  id?: number | string;
  attachmentId?: string;
  visibility?: "personal" | "organization" | "roles" | "link";
  src: string;
  name: string;
  showFloatingButtons: boolean;
  onDelete: () => void;
}) => {
  const { t } = useTranslation();
  const [previewOpened, setPreviewOpened] = useState(false);
  const [detailsOpened, { open: openDetails, close: closeDetails }] =
    useDisclosure(false);
  const fileId = resolveAttachmentFileId(attachmentId, id);

  if (!showFloatingButtons) {
    return (
      <>
        <div className="thumbnail pointer flex-shrink-0">
          <img
            onClick={openDetails}
            src={src}
            alt={`attachment-${name}`}
            className="max-w-[70px] max-h-[70px] w-[70px] h-[70px] object-contain rounded-md flex-shrink-0"
          />
        </div>
        <AttachmentDetailsModal
          opened={detailsOpened}
          onClose={closeDetails}
          attachmentId={fileId}
          fallbackName={name}
          fallbackUrl={src}
          initialItem={detailsInitialItem({
            fileId,
            src,
            name,
            visibility,
            type: "image",
            contentType: "image/*",
          })}
        />
      </>
    );
  }

  return (
    <div className="width-150 document-attachment bg-contrast rounded padding-small">
      {previewOpened && (
        <ImageModal src={src} name={name} hide={() => setPreviewOpened(false)} />
      )}
      <div className="d-flex gap-small align-center">
        <img
          onClick={() => setPreviewOpened(true)}
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

const SignatureRequestThumbnail = ({
  url,
  name,
  status,
  signatoryName,
}: {
  url: string;
  name: string;
  status?: string;
  signatoryName?: string;
}) => {
  const { t } = useTranslation();
  const safeUrl = url || "";
  const isSigned = status === "signed";
  const statusLabel = isSigned
    ? t("signature-request-signed")
    : t("signature-request-pending");

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
      {isSigned ? (
        <IconCircleCheck size={20} color="var(--mantine-color-green-6, #2f9e44)" />
      ) : (
        <IconSignature size={20} />
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p className="cut-text-to-line" style={{ margin: 0 }}>
          {name || t("signature-request-default-title")}
        </p>
        <p
          className="cut-text-to-line"
          style={{ margin: 0, fontSize: 12, opacity: 0.7 }}
        >
          {statusLabel}
          {signatoryName ? ` · ${signatoryName}` : ""}
        </p>
      </div>
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
  name,
  src,
  onDelete,
  id,
  attachmentId,
  visibility,
  showFloatingButtons,
}: {
  index: number;
  name: string;
  src: string;
  onDelete: () => void;
  id?: number | string;
  attachmentId?: string;
  visibility?: "personal" | "organization" | "roles" | "link";
  showFloatingButtons: boolean;
}) => {
  const [opened, { open, close }] = useDisclosure(false);
  const fileId = resolveAttachmentFileId(attachmentId, id);

  if (showFloatingButtons) {
    return (
      <div
        title={name}
        className="width-150 document-attachment bg-contrast rounded padding-small"
      >
        <div className="d-flex gap-small align-center">
          <DocumentFileIcon name={name} size={20} />
          <p className="cut-text-to-line" style={{ margin: 0, flex: 1, minWidth: 0 }}>
            {name}
          </p>
          <ActionIcon
            variant="subtle"
            color="red"
            size="sm"
            onClick={onDelete}
          >
            <IconX size={16} />
          </ActionIcon>
        </div>
      </div>
    );
  }

  return (
    <>
      <UnstyledButton
        onClick={open}
        title={name}
        aria-label={name}
        className="width-150 document-attachment bg-contrast rounded padding-small"
        style={{
          display: "inline-flex",
          width: 150,
          maxWidth: "100%",
          alignSelf: "flex-start",
          textAlign: "left",
          cursor: "pointer",
        }}
      >
        <div className="d-flex gap-small align-center" style={{ width: "100%", minWidth: 0 }}>
          <DocumentFileIcon name={name} size={20} />
          <p className="cut-text-to-line" style={{ margin: 0, flex: 1, minWidth: 0 }}>
            {name}
          </p>
        </div>
      </UnstyledButton>
      <AttachmentDetailsModal
        opened={opened}
        onClose={close}
        attachmentId={fileId}
        fallbackName={name}
        fallbackUrl={src}
        initialItem={detailsInitialItem({
          fileId,
          src,
          name,
          visibility,
          type: "document",
        })}
      />
    </>
  );
};

const resolveVideoUrl = (src: string) => {
  if (!src) return src;
  if (src.startsWith("http://") || src.startsWith("https://") || src.startsWith("data:")) return src;
  return `${API_URL}${src.startsWith("/") ? "" : "/"}${src}`;
};

const VideoAttachmentThumbnail = ({
  id,
  attachmentId,
  visibility,
  src,
  name,
  text,
  showFloatingButtons,
  onDelete,
}: {
  id?: number | string;
  attachmentId?: string;
  visibility?: "personal" | "organization" | "roles" | "link";
  src: string;
  name: string;
  text?: string;
  showFloatingButtons: boolean;
  onDelete: () => void;
}) => {
  const { t } = useTranslation();
  const [previewOpened, setPreviewOpened] = useState(false);
  const [detailsOpened, { open: openDetails, close: closeDetails }] =
    useDisclosure(false);
  const videoUrl = resolveVideoUrl(src);
  const fileId = resolveAttachmentFileId(attachmentId, id);

  const preview = (
    <video
      src={videoUrl}
      muted
      playsInline
      preload="metadata"
      tabIndex={0}
      aria-label={name}
      onClick={() => {
        if (showFloatingButtons) setPreviewOpened(true);
        else openDetails();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          if (showFloatingButtons) setPreviewOpened(true);
          else openDetails();
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
      <>
        <div className="thumbnail pointer flex-shrink-0">{preview}</div>
        <AttachmentDetailsModal
          opened={detailsOpened}
          onClose={closeDetails}
          attachmentId={fileId}
          fallbackName={name}
          fallbackUrl={videoUrl}
          initialItem={detailsInitialItem({
            fileId,
            src: videoUrl,
            name,
            visibility,
            type: "video",
            contentType: "video/*",
          })}
        />
      </>
    );
  }

  return (
    <div className="width-150 document-attachment bg-contrast rounded padding-small">
      {previewOpened && (
        <VideoModal
          url={videoUrl}
          name={name}
          close={() => setPreviewOpened(false)}
          text={text}
        />
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

const AudioThumbnail = ({
  id,
  attachmentId,
  visibility,
  src,
  name,
  showFloatingButtons,
  onDelete,
}: {
  id?: number | string;
  attachmentId?: string;
  visibility?: "personal" | "organization" | "roles" | "link";
  src: string;
  name: string;
  showFloatingButtons: boolean;
  onDelete: () => void;
}) => {
  const audioUrl =
    !src
      ? ""
      : src.startsWith("http://") ||
          src.startsWith("https://") ||
          src.startsWith("data:")
        ? src
        : `${API_URL}${src.startsWith("/") ? "" : "/"}${src}`;
  const [opened, { open, close }] = useDisclosure(false);
  const fileId = resolveAttachmentFileId(attachmentId, id);
  const label = (name || "").trim() || "audio";

  if (showFloatingButtons) {
    return (
      <div
        title={label}
        className="width-150 document-attachment bg-contrast rounded padding-small"
      >
        <div className="d-flex gap-small align-center">
          <IconMusic size={20} />
          <p className="cut-text-to-line" style={{ margin: 0, flex: 1, minWidth: 0 }}>
            {label}
          </p>
          <ActionIcon
            variant="subtle"
            color="red"
            size="sm"
            onClick={onDelete}
          >
            <IconX size={16} />
          </ActionIcon>
        </div>
      </div>
    );
  }

  return (
    <>
      <UnstyledButton
        onClick={open}
        title={label}
        aria-label={label}
        className="width-150 document-attachment bg-contrast rounded padding-small"
        style={{
          display: "inline-flex",
          width: 150,
          maxWidth: "100%",
          alignSelf: "flex-start",
          textAlign: "left",
          cursor: "pointer",
        }}
      >
        <div className="d-flex gap-small align-center" style={{ width: "100%", minWidth: 0 }}>
          <IconMusic size={20} />
          <p className="cut-text-to-line" style={{ margin: 0, flex: 1, minWidth: 0 }}>
            {label}
          </p>
        </div>
      </UnstyledButton>
      <AttachmentDetailsModal
        opened={opened}
        onClose={close}
        attachmentId={fileId}
        fallbackName={label}
        fallbackUrl={audioUrl}
        initialItem={detailsInitialItem({
          fileId,
          src: audioUrl,
          name: label,
          visibility,
          type: "audio",
          contentType: "audio/*",
        })}
      />
    </>
  );
};
