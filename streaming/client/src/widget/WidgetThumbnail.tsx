/**
 * Lightweight read-only thumbnail for the chat widget.
 * Completely isolated from the main app — no store, no i18n, no Mantine.
 */
import React, { useRef, useState } from "react";
import { API_URL } from "../modules/constants";

const WIDGET_VIDEO_EXT = /\.(mp4|webm|mov|m4v|ogv)(\?|#|$)/i;

function isWidgetVideoType(type: string, name: string): boolean {
  const t = type || "";
  if (t.startsWith("video/") || t.startsWith("video_generation")) return true;
  if (t.startsWith("image") || t.startsWith("audio")) return false;
  return WIDGET_VIDEO_EXT.test(name || "");
}

interface WidgetThumbnailProps {
  src: string;
  type: string;
  content: string;
  name: string;
  index: number;
  text?: string;
  message_id?: number;
}

export const WidgetThumbnail: React.FC<WidgetThumbnailProps> = ({
  src,
  type,
  content,
  name,
  text,
}) => {
  if (type.startsWith("image")) {
    const imageSrc =
      src.startsWith("http") ||
      src.startsWith("https") ||
      src.startsWith("data:")
        ? src
        : `${API_URL}${src.startsWith("/") ? src : `/${src}`}`;
    return <WidgetImageThumbnail src={imageSrc} name={name} />;
  }

  if (type.startsWith("audio_generation") || type.startsWith("audio")) {
    const audioSrc = content.startsWith("http") || content.startsWith("data:")
      ? content
      : `${API_URL}${content.startsWith("/") ? content : `/${content}`}`;
    return <WidgetAudioThumbnail src={audioSrc} />;
  }

  if (isWidgetVideoType(type, name)) {
    const videoSrc =
      src.startsWith("http") || src.startsWith("https") || src.startsWith("data:")
        ? src
        : `${API_URL}${src.startsWith("/") ? src : `/${src}`}`;
    return <WidgetVideoThumbnail src={videoSrc} name={name} text={text} />;
  }

  if (type === "website") {
    return (
      <a
        href={src || content}
        target="_blank"
        rel="noopener noreferrer"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          padding: "4px 10px",
          borderRadius: 6,
          background: "rgba(255,255,255,0.08)",
          color: "inherit",
          textDecoration: "none",
          fontSize: 13,
          maxWidth: 200,
          overflow: "hidden",
          textOverflow: "ellipsis",
          whiteSpace: "nowrap",
        }}
      >
        🔗 {name || src || content}
      </a>
    );
  }

  const documentHref =
    src && (src.startsWith("http") || src.startsWith("data:"))
      ? src
      : `${API_URL}${(src || content).startsWith("/") ? "" : "/"}${src || content}`;

  return (
    <a
      href={documentHref}
      download={name || "document"}
      target="_blank"
      rel="noopener noreferrer"
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: "4px 10px",
        borderRadius: 6,
        background: "rgba(255,255,255,0.08)",
        fontSize: 13,
        maxWidth: 200,
        overflow: "hidden",
        textOverflow: "ellipsis",
        whiteSpace: "nowrap",
        color: "inherit",
        textDecoration: "none",
      }}
    >
      📄 {name}
    </a>
  );
};

const WidgetImageThumbnail: React.FC<{ src: string; name: string }> = ({ src, name }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <img
        onClick={() => setExpanded(true)}
        src={src}
        alt={name}
        style={{
          maxWidth: 70,
          maxHeight: 70,
          width: 70,
          height: 70,
          objectFit: "contain",
          borderRadius: 6,
          cursor: "pointer",
          flexShrink: 0,
        }}
      />
      {expanded && (
        <div
          onClick={() => setExpanded(false)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            background: "rgba(0,0,0,0.8)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            cursor: "zoom-out",
          }}
        >
          <img
            src={src}
            alt={name}
            style={{ maxWidth: "90%", maxHeight: "90%", objectFit: "contain", borderRadius: 8 }}
          />
        </div>
      )}
    </>
  );
};

const WidgetAudioThumbnail: React.FC<{ src: string }> = ({ src }) => {
  const audioRef = useRef<HTMLAudioElement>(null);
  return <audio ref={audioRef} controls src={src} playsInline style={{ maxWidth: "100%" }} />;
};

const WidgetVideoThumbnail: React.FC<{ src: string; name: string; text?: string }> = ({
  src,
  name,
  text,
}) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <video
        src={src}
        muted
        playsInline
        preload="metadata"
        aria-label={name}
        onClick={() => setExpanded(true)}
        style={{
          maxWidth: 70,
          maxHeight: 70,
          width: 70,
          height: 70,
          objectFit: "cover",
          borderRadius: 6,
          cursor: "pointer",
          flexShrink: 0,
          background: "rgba(0,0,0,0.35)",
        }}
      />
      {expanded && (
        <div
          onClick={() => setExpanded(false)}
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 9999,
            background: "rgba(0,0,0,0.85)",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            cursor: "pointer",
            padding: 20,
          }}
        >
          <video
            src={src}
            controls
            autoPlay
            playsInline
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "90%", maxHeight: "80vh", borderRadius: 8, cursor: "default" }}
          />
          {text && <p style={{ color: "#aaa", marginTop: 8, fontSize: 13 }}>{text}</p>}
        </div>
      )}
    </>
  );
};
