/**
 * Lightweight markdown renderer for the chat widget.
 * Completely isolated from the main app — no store, no plugins, no i18n.
 */
import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { twilight } from "react-syntax-highlighter/dist/esm/styles/prism";

const WIDGET_API_URL =
  // @ts-ignore
  import.meta.env.VITE_API_URL || "http://localhost:8000";

interface WidgetMarkdownRendererProps {
  markdown: string;
  extraClass?: string;
  attachments?: { attachment_id?: string | number; id?: string | number; content?: string }[];
}

const WidgetMarkdownRenderer: React.FC<WidgetMarkdownRendererProps> = ({
  markdown,
  extraClass,
  attachments,
}) => {
  const attachmentUrlById = new Map<string, string>();
  for (const att of attachments || []) {
    const id = (att.attachment_id || att.id) as string | number | undefined;
    const content = att.content;
    if (!id || !content) continue;
    attachmentUrlById.set(String(id), String(content));
  }

  const normalizeUrl = (url: string) => {
    const u = (url || "").trim();
    if (!u) return u;
    if (u.startsWith("http://") || u.startsWith("https://") || u.startsWith("data:")) return u;
    if (u.startsWith("/")) return `${WIDGET_API_URL}${u}`;
    return u;
  };

  const urlTransform = (url: string) => {
    const u = (url || "").trim();
    if (!u) return u;
    if (u.toLowerCase().startsWith("attachment:")) {
      const id = u.slice("attachment:".length).trim();
      const resolved = id ? attachmentUrlById.get(id) : undefined;
      return resolved ? normalizeUrl(resolved) : u;
    }
    if (u.startsWith("/media/")) return `${WIDGET_API_URL}${u}`;
    return u;
  };

  return (
    <Markdown
      className={`markdown-renderer ${extraClass || ""}`}
      urlTransform={urlTransform}
      remarkPlugins={[[remarkGfm, { singleTilde: false }]]}
      skipHtml={true}
      components={{
        img(props) {
          const src = (props as any)?.src as string | undefined;
          const alt = (props as any)?.alt as string | undefined;
          const resolvedSrc = src ? urlTransform(src) : src;
          return (
            <img
              {...(props as any)}
              src={resolvedSrc}
              alt={alt || ""}
              style={{ maxWidth: "100%", borderRadius: 8, ...((props as any)?.style || {}) }}
            />
          );
        },
        a(props) {
          const href = (props as any)?.href as string | undefined;
          const resolvedHref = href ? urlTransform(href) : href;
          return (
            <a
              {...(props as any)}
              href={resolvedHref}
              target={(resolvedHref || "").includes("#") ? undefined : "_blank"}
              rel="noopener noreferrer"
            />
          );
        },
        pre(props) {
          const codeBlocks = props.node?.children.map((child) => {
            // @ts-ignore
            const code = child.children.map((c) => c.value).join("");
            // @ts-ignore
            const classNames = child.properties?.className;
            let lang = "text";
            if (classNames && classNames?.length > 0) {
              lang = classNames[0].split("-")[1];
            }
            return { lang, code };
          });
          if (!codeBlocks || codeBlocks.length === 0) {
            return <pre>{props.children}</pre>;
          }
          return (
            <WidgetCodeBlock code={codeBlocks[0].code} language={codeBlocks[0].lang} />
          );
        },
      }}
    >
      {markdown}
    </Markdown>
  );
};

const WidgetCodeBlock = ({ code, language }: { code: string; language: string }) => {
  const handleCopy = () => {
    navigator.clipboard.writeText(code);
  };

  return (
    <div style={{ position: "relative" }}>
      <button
        onClick={handleCopy}
        style={{
          position: "absolute",
          top: 4,
          right: 4,
          background: "rgba(255,255,255,0.15)",
          border: "none",
          borderRadius: 4,
          padding: "2px 8px",
          cursor: "pointer",
          color: "#ccc",
          fontSize: 11,
        }}
      >
        Copy
      </button>
      <SyntaxHighlighter language={language || "text"} style={twilight}>
        {code}
      </SyntaxHighlighter>
    </div>
  );
};

export default WidgetMarkdownRenderer;
