import React, { useEffect, useState } from "react";
import "./HtmlFrame.css";

// Do not add allow-same-origin. The page could then see who is signed in.
const HTML_FRAME_SANDBOX =
  "allow-scripts allow-forms allow-modals allow-popups allow-popups-to-escape-sandbox allow-downloads allow-pointer-lock";

export type HtmlAttachmentRef = {
  name?: string;
  content?: string;
  type?: string;
};

function filePath(url: string): string {
  const trimmed = url.trim();
  if (!trimmed || trimmed.toLowerCase().startsWith("data:")) return trimmed;
  const noQuery = trimmed.split(/[?#]/)[0];
  if (!noQuery.startsWith("http://") && !noQuery.startsWith("https://")) return noQuery;
  const scheme = noQuery.indexOf("//");
  const slash = noQuery.indexOf("/", scheme + 2);
  return slash === -1 ? "/" : noQuery.slice(slash);
}

function fileNameFromPath(url: string): string {
  return filePath(url).split("/").pop() || "file.html";
}

export function isHtmlFile(name = "", url = "", contentType = ""): boolean {
  const ct = contentType.toLowerCase().split(";")[0].trim();
  if (ct === "text/html") return true;
  const lowerName = name.toLowerCase().split(/[?#]/)[0];
  if (lowerName.endsWith(".html") || lowerName.endsWith(".htm")) return true;
  const path = filePath(url).toLowerCase();
  if (path.startsWith("data:text/html")) return true;
  return path.endsWith(".html") || path.endsWith(".htm");
}

function sameStoredFile(a: string, b: string): boolean {
  if (a === b) return true;
  const left = filePath(a);
  const right = filePath(b);
  return left.length > 1 && left === right;
}

export function htmlPreviewFromHref(
  href: string,
  attachments: HtmlAttachmentRef[] | undefined,
  resolveUrl: (content: string) => string,
): { src: string; name: string } | null {
  const target = (href || "").trim();
  if (!target) return null;
  for (const att of attachments || []) {
    if (!att.content) continue;
    const src = resolveUrl(String(att.content));
    if (!src || !sameStoredFile(src, target)) continue;
    if (!isHtmlFile(att.name || "", src, att.type || "")) continue;
    return { src, name: att.name || fileNameFromPath(src) };
  }
  const path = filePath(target).toLowerCase();
  if (path.includes("/message_attachments/") && isHtmlFile("", target)) {
    return { src: target, name: fileNameFromPath(target) };
  }
  return null;
}

export function linkText(node: React.ReactNode): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(linkText).join("");
  if (React.isValidElement(node)) {
    const props = node.props as { children?: React.ReactNode };
    return linkText(props.children);
  }
  return "";
}

export function useHtmlFrameSrc(src: string): { frameSrc: string; loading: boolean } {
  const [frameSrc, setFrameSrc] = useState("");
  const [loading, setLoading] = useState(Boolean(src));

  useEffect(() => {
    if (!src) {
      setFrameSrc("");
      setLoading(false);
      return;
    }
    if (src.startsWith("blob:")) {
      setFrameSrc(src);
      setLoading(false);
      return;
    }
    let cancelled = false;
    let created = "";
    setLoading(true);
    const run = async () => {
      try {
        const res = await fetch(src);
        if (!res.ok) throw new Error(String(res.status));
        const html = await res.text();
        if (cancelled) return;
        created = URL.createObjectURL(new Blob([html], { type: "text/html" }));
        if (cancelled) {
          URL.revokeObjectURL(created);
          created = "";
          return;
        }
        setFrameSrc(created);
      } catch {
        if (!cancelled) setFrameSrc(src);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void run();
    return () => {
      cancelled = true;
      if (created) URL.revokeObjectURL(created);
    };
  }, [src]);

  return { frameSrc, loading };
}

export function HtmlFrame({
  src,
  title,
  height,
}: {
  src: string;
  title: string;
  height: number | string;
}) {
  const { frameSrc, loading } = useHtmlFrameSrc(src);
  return (
    <span className="html-frame" style={{ height }}>
      {loading && (
        <span className="html-frame-loading">
          <span className="html-frame-spinner" />
        </span>
      )}
      {frameSrc && (
        <iframe title={title} src={frameSrc} sandbox={HTML_FRAME_SANDBOX} />
      )}
    </span>
  );
}
