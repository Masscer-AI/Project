/**
 * Lightweight read-only thumbnail for the chat widget.
 * Completely isolated from the main app — no store, no i18n, no Mantine.
 */
import React, { useRef, useState } from "react";

const WIDGET_API_URL =
  // @ts-ignore
  import.meta.env.VITE_API_URL || "http://localhost:8000";

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
    return <WidgetImageThumbnail src={src} name={name} />;
  }

  if (type.startsWith("audio_generation") || type.startsWith("audio")) {
    const audioSrc = content.startsWith("http") || content.startsWith("data:")
      ? content
      : `${WIDGET_API_URL}${content}`;
    return <WidgetAudioThumbnail src={audioSrc} />;
  }

  if (type.startsWith("video_generation")) {
    const videoSrc = src.startsWith("http") || src.startsWith("data:")
      ? src
      : `${WIDGET_API_URL}${src}`;
    return <WidgetVideoThumbnail src={videoSrc} text={text} />;
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

  return (
    <div
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
      }}
    >
      📄 {name}
    </div>
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

const WidgetVideoThumbnail: React.FC<{ src: string; text?: string }> = ({ src, text }) => {
  const [expanded, setExpanded] = useState(false);

  return (
    <>
      <button
        onClick={() => setExpanded(true)}
        style={{
          background: "rgba(255,255,255,0.1)",
          border: "none",
          borderRadius: 6,
          padding: "6px 12px",
          cursor: "pointer",
          color: "inherit",
          fontSize: 13,
        }}
      >
        ▶ Video
      </button>
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
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "90%", maxHeight: "80vh", borderRadius: 8, cursor: "default" }}
          />
          {text && <p style={{ color: "#aaa", marginTop: 8, fontSize: 13 }}>{text}</p>}
        </div>
      )}
    </>
  );
};
