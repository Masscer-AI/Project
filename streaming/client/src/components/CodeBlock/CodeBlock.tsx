import React, { useCallback, useEffect, useRef, useState } from "react";
import mermaid from "mermaid";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import "./CodeBlock.css";
import toast from "react-hot-toast";
import { ActionIcon, Group, Modal, Tooltip } from "@mantine/core";
import {
  IconDownload,
  IconMaximize,
  IconZoomIn,
  IconZoomOut,
  IconZoomReset,
} from "@tabler/icons-react";

export const CodeBlock = ({
  code,
  language,
}: {
  code: string;
  language: string;
}) => {
  if (language === "mermaid") {
    return <MermaidVisualizer code={code} />;
  }
  toast.success("Mermaid visualizer is not available yet");
  return <pre className={`language-${language}`}>{code}</pre>;
};

let mermaidIdCounter = 0;

const MermaidVisualizer = ({ code }: { code: string }) => {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const [svgContent, setSvgContent] = useState<string>("");

  const { theming } = useStore((s) => ({
    theming: s.theming,
  }));

  useEffect(() => {
    mermaid.initialize({ startOnLoad: false, theme: theming.mermaid as any });
    renderDiagram();
  }, [code, theming.mermaid]);

  const renderDiagram = async () => {
    try {
      const id = `mermaid-diagram-${mermaidIdCounter++}`;
      const { svg } = await mermaid.render(id, code);
      setSvgContent(svg);
    } catch (error) {
      console.error("Mermaid render error:", error);
      setSvgContent("");
    }
  };

  const downloadSVG = () => {
    if (!svgContent) return;
    const blob = new Blob([svgContent], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "diagram.svg";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex-y gap-medium mermaid-container">
      {svgContent ? (
        <PanZoomViewer svgContent={svgContent} height="400px" />
      ) : (
        <pre className="mermaid">{code}</pre>
      )}

      <Group gap="xs" justify="center">
        <Tooltip label={t("download-svg")} position="top" withArrow>
          <ActionIcon variant="default" size="sm" onClick={downloadSVG}>
            <IconDownload size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label={t("expand")} position="top" withArrow>
          <ActionIcon variant="default" size="sm" onClick={() => setExpanded(true)}>
            <IconMaximize size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>

      <Modal
        opened={expanded}
        onClose={() => setExpanded(false)}
        title={t("mermaid-visualizer")}
        size="95vw"
        centered
        styles={{
          body: { padding: 0, overflow: "hidden" },
          content: { maxHeight: "90vh" },
        }}
      >
        {svgContent && <PanZoomViewer svgContent={svgContent} height="75vh" />}
      </Modal>
    </div>
  );
};

/** Make SVG inside the container fill its width so diagrams are readable by default. */
function fitSvgToWidth(rawSvg: string): string {
  return rawSvg
    .replace(/<svg([^>]*)width="[^"]*"/, '<svg$1width="100%"')
    .replace(/<svg([^>]*)height="[^"]*"/, '<svg$1height="auto"');
}

function PanZoomViewer({ svgContent, height = "75vh" }: { svgContent: string; height?: string }) {
  const { t } = useTranslation();
  const containerRef = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const isDragging = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });

  const fittedSvg = fitSvgToWidth(svgContent);

  const MIN_SCALE = 0.2;
  const MAX_SCALE = 5;

  // Use a native wheel listener with { passive: false } so we can actually
  // preventDefault and stop the chat page from scrolling while zooming.
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const handler = (e: WheelEvent) => {
      e.preventDefault();
      e.stopPropagation();
      const delta = e.deltaY > 0 ? -0.1 : 0.1;
      setScale((prev) => Math.min(MAX_SCALE, Math.max(MIN_SCALE, prev + delta)));
    };
    el.addEventListener("wheel", handler, { passive: false });
    return () => el.removeEventListener("wheel", handler);
  }, []);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button !== 0) return;
    isDragging.current = true;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    e.preventDefault();
  }, []);

  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isDragging.current) return;
    const dx = e.clientX - lastMouse.current.x;
    const dy = e.clientY - lastMouse.current.y;
    lastMouse.current = { x: e.clientX, y: e.clientY };
    setTranslate((prev) => ({ x: prev.x + dx, y: prev.y + dy }));
  }, []);

  const handleMouseUp = useCallback(() => {
    isDragging.current = false;
  }, []);

  const zoomIn = () => setScale((s) => Math.min(MAX_SCALE, s + 0.25));
  const zoomOut = () => setScale((s) => Math.max(MIN_SCALE, s - 0.25));
  const resetView = () => {
    setScale(1);
    setTranslate({ x: 0, y: 0 });
  };

  return (
    <div style={{ position: "relative", borderRadius: 8, overflow: "hidden" }}>
      {/* Controls */}
      <Group
        gap={4}
        style={{
          position: "absolute",
          top: 8,
          right: 8,
          zIndex: 10,
          background: "rgba(0,0,0,0.6)",
          backdropFilter: "blur(4px)",
          borderRadius: 8,
          padding: 4,
        }}
      >
        <Tooltip label={t("zoom-in") || "Zoom in"} position="bottom" withArrow>
          <ActionIcon variant="subtle" color="gray" size="sm" onClick={zoomIn}>
            <IconZoomIn size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label={t("zoom-out") || "Zoom out"} position="bottom" withArrow>
          <ActionIcon variant="subtle" color="gray" size="sm" onClick={zoomOut}>
            <IconZoomOut size={16} />
          </ActionIcon>
        </Tooltip>
        <Tooltip label={t("reset") || "Reset"} position="bottom" withArrow>
          <ActionIcon variant="subtle" color="gray" size="sm" onClick={resetView}>
            <IconZoomReset size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>

      {/* Pan-zoom area */}
      <div
        ref={containerRef}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onMouseLeave={handleMouseUp}
        style={{
          width: "100%",
          height,
          overflow: "hidden",
          cursor: isDragging.current ? "grabbing" : "grab",
          userSelect: "none",
        }}
      >
        <div
          dangerouslySetInnerHTML={{ __html: fittedSvg }}
          style={{
            width: "100%",
            transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})`,
            transformOrigin: "top center",
            transition: isDragging.current ? "none" : "transform 0.1s ease-out",
          }}
        />
      </div>
    </div>
  );
}
