import React, { useEffect, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { twilight } from "react-syntax-highlighter/dist/esm/styles/prism";

import toast from "react-hot-toast";
import "./MarkdownRenderer.css";
import { downloadFile, generateDocument } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";
import { Badge, ActionIcon, Tooltip, NativeSelect, Group, Button } from "@mantine/core";
import { IconCopy, IconDownload } from "@tabler/icons-react";

import { SYSTEM_PLUGINS } from "../../modules/plugins";
import { API_URL } from "../../modules/constants";
import { TAttachment } from "../../types";

const MarkdownRenderer = ({
  markdown,
  extraClass,
  onChange,
  attachments,
}: {
  markdown: string;
  extraClass?: string;
  onChange?: (markdown: string) => void;
  attachments?: TAttachment[];
}) => {
  const { t } = useTranslation();

  const attachmentUrlById = (() => {
    const map = new Map<string, string>();
    for (const att of attachments || []) {
      const id = (att.attachment_id || att.id) as string | number | undefined;
      const content = att.content;
      if (!id || !content) continue;
      map.set(String(id), String(content));
    }
    return map;
  })();

  const attachmentMetaById = (() => {
    const map = new Map<string, { type?: string; name?: string; content?: string }>();
    for (const att of attachments || []) {
      const id = (att.attachment_id || att.id) as string | number | undefined;
      if (!id) continue;
      map.set(String(id), {
        type: att.type,
        name: att.name,
        content: att.content,
      });
    }
    return map;
  })();

  const normalizeUrl = (url: string) => {
    const u = (url || "").trim();
    if (!u) return u;
    if (u.startsWith("http://") || u.startsWith("https://") || u.startsWith("data:")) {
      return u;
    }
    if (u.startsWith("/")) {
      return `${API_URL}${u}`;
    }
    return u;
  };

  // react-markdown URL rewrite hook (for links + images)
  const urlTransform = (url: string) => {
    const u = (url || "").trim();
    if (!u) return u;

    // Preferred: attachment UUID reference
    // Example: ![Alt](attachment:550e8400-e29b-41d4-a716-446655440000)
    if (u.toLowerCase().startsWith("attachment:")) {
      const id = u.slice("attachment:".length).trim();
      const resolved = id ? attachmentUrlById.get(id) : undefined;
      return resolved ? normalizeUrl(resolved) : u;
    }

    // Legacy: model sometimes outputs /media/... which needs API_URL prefix
    if (u.startsWith("/media/")) {
      return `${API_URL}${u}`;
    }

    return u;
  };

  const changeInMarkdown = (search: string, replace: string) => {
    const newMarkdown = markdown.replace(search, replace);
    if (onChange) {
      onChange(newMarkdown);
    }
  };

  return (
    <Markdown
      className={`markdown-renderer ${extraClass}`}
      urlTransform={urlTransform}
      remarkPlugins={[
        [remarkGfm, { singleTilde: false }],
        [remarkMath],
        // [docx, { output: "blob" }],
      ]}
      rehypePlugins={[rehypeKatex]}
      skipHtml={true}
      components={{
        img(props) {
          // react-markdown passes src/alt on props
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const src = (props as any)?.src as string | undefined;
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const alt = (props as any)?.alt as string | undefined;
          const resolvedSrc = src ? urlTransform(src) : src;

          const rawId =
            src && src.toLowerCase().startsWith("attachment:")
              ? src.slice("attachment:".length).trim()
              : "";
          const meta = rawId ? attachmentMetaById.get(rawId) : undefined;
          const typeHint = (meta?.type || "").toLowerCase();
          const looksLikeDocumentUrl = !!resolvedSrc && /\.(pdf|doc|docx|xls|xlsx|ppt|pptx|csv|txt)(\?|$)/i.test(resolvedSrc);
          const isNonImageAttachment =
            typeHint === "document" || typeHint === "rag_document" || looksLikeDocumentUrl;
          const unresolvedAttachmentRef =
            !!src && src.toLowerCase().startsWith("attachment:") && resolvedSrc === src;

          // If the model used image markdown for a non-image attachment
          // (very common with PDFs), render it as a file link instead.
          if (isNonImageAttachment && resolvedSrc) {
            const label = alt || meta?.name || t("open-attachment") || "Open attachment";
            return (
              <a href={resolvedSrc} target="_blank" rel="noopener noreferrer">
                {label}
              </a>
            );
          }

          // Avoid browser GET attachment:... for unresolved refs.
          if (unresolvedAttachmentRef) {
            const label = alt || t("attachment-not-found") || "Attachment not found";
            return <span>{label}</span>;
          }

          return (
            <img
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              {...(props as any)}
              src={resolvedSrc}
              alt={alt || ""}
              style={{
                maxWidth: "100%",
                borderRadius: 8,
                ...(// eslint-disable-next-line @typescript-eslint/no-explicit-any
                ((props as any)?.style || {})),
              }}
            />
          );
        },
        a(props) {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          const href = (props as any)?.href as string | undefined;
          const resolvedHref = href ? urlTransform(href) : href;
          return (
            <a
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
            return {
              lang,
              code,
            };
          });
          if (!codeBlocks || codeBlocks.length === 0) {
            // toast.success("No code blocks found");
            return <pre>{props.children}</pre>;
          }
          return (
            <CustomCodeBlock
              code={codeBlocks[0].code}
              language={codeBlocks[0].lang}
              changeInMarkdown={changeInMarkdown}
            />
          );
        },
      }}
    >
      {markdown}
    </Markdown>
  );
};

const output_formats = [
  "docx",
  "pdf",
  "md",
  "csv",
  "html",
  "json",
  "txt",
  "latex",
];
type TOutputFormat =
  | "docx"
  | "pdf"
  | "md"
  | "csv"
  | "html"
  | "json"
  | "txt"
  | "latex";

const text_only_formats = ["csv", "txt", "json", "latex"];

const downloadTextAsFile = (text: string, format: TOutputFormat) => {
  // Download the text as a CSV file
  const blob = new Blob([text], { type: "text/csv" });
  // use as title the first 50 characters of the text
  const title = text.slice(0, 50);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${title}.${format}`;
  a.click();
};

export const CustomCodeBlock = ({
  code,
  language,
  changeInMarkdown,
}: {
  code: string;
  language: string;
  changeInMarkdown: (search: string, replace: string) => void;
}) => {
  const { t } = useTranslation();
  const [output_format, setOutputFormat] = useState<TOutputFormat>("docx");
  const [input_format, setInputFormat] = useState("md");
  const [usePlugin, setUsePlugin] = useState<boolean>(false);
  const [pluginName, setPluginName] = useState<string | null>(null);

  useEffect(() => {
    // If the language is HTML, set the output format to HTML
    if (language === "html") {
      setInputFormat("html");
    }
    if (language === "latex") {
      setInputFormat("latex");
    }

    if (language === "mermaid") {
      setPluginName("mermaid");
      setUsePlugin(true);
    }

    if (language === "json") {
      findPlugin();
    }

    if (language === "documentMaker") {
      setPluginName("documentMaker");
      setUsePlugin(true);
    }
  }, [code, language]);

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    toast.success(t("code-copied-to-clipboard"));
  };

  const handleTransform = async () => {
    if (code) {
      if (text_only_formats.includes(output_format)) {
        downloadTextAsFile(code, output_format);
        return;
      }
      const tid = toast.loading(t("generating-document"));

      try {
        const res = await generateDocument({
          source_text: code,
          from_type: input_format,
          to_type: output_format,
        });
        toast.success(t("document-generated"), {
          id: tid,
        });
        // @ts-ignore
        const success = await downloadFile(res.output_filepath);
        if (!success) {
          toast.dismiss(tid);
          toast.error(t("error-downloading-document"));
        }
        toast.success(t("document-downloaded"), {
          id: tid,
        });
      } catch (e) {
        toast.dismiss(tid);
        toast.error(t("error-generating-document"));
      }
    } else {
      toast.error("No code available!");
    }
  };

  const findPlugin = () => {
    try {
      const json = JSON.parse(code);
      if (json.plugin) {
        // setUsePlugin(true);
        setPluginName(json.plugin);
      }
    } catch (e) {
      console.log(e);
      setUsePlugin(false);
      setPluginName(null);
    }
  };

  const label = usePlugin ? pluginName : language;

  return (
    <div className="code-block">
      <Group
        gap="xs"
        justify="space-between"
        wrap="wrap"
        className="actions bg-hovered rounded"
        p="xs"
      >
        <Badge variant="default" size="sm">
          {label?.slice(0, 1).toUpperCase() + (label ? label.slice(1) : "")}
        </Badge>
        <Group gap={4} wrap="wrap" justify="flex-end">
          <Tooltip label={t("copy")} position="top" withArrow>
            <ActionIcon variant="subtle" color="gray" size="sm" onClick={handleCopy}>
              <IconCopy size={14} />
            </ActionIcon>
          </Tooltip>
          {pluginName && (
            <Button
              variant="subtle"
              color="gray"
              size="compact-xs"
              onClick={usePlugin ? () => setUsePlugin(false) : () => setUsePlugin(true)}
            >
              {usePlugin ? t("view-code") : t("use-plugin") + ": " + t(pluginName)}
            </Button>
          )}
          <Group gap={2} wrap="nowrap">
            <Tooltip label={t("export-to")} position="top" withArrow>
              <ActionIcon variant="subtle" color="gray" size="sm" onClick={handleTransform}>
                <IconDownload size={14} />
              </ActionIcon>
            </Tooltip>
            <NativeSelect
              size="xs"
              value={output_format}
              onChange={(e) => setOutputFormat(e.currentTarget.value as TOutputFormat)}
              data={output_formats.map((f) => ({ value: f, label: f.toUpperCase() }))}
              styles={{ input: { minWidth: 60, height: 28, fontSize: 12 } }}
            />
          </Group>
        </Group>
      </Group>

      {pluginName && usePlugin ? (
        SYSTEM_PLUGINS[pluginName]?.code_receptor ? (
          SYSTEM_PLUGINS[pluginName].code_receptor(code, language)
        ) : (
          <SyntaxHighlighter
            language={language ? language : "text"}
            style={twilight}
          >
            {code}
          </SyntaxHighlighter>
        )
      ) : (
        <SyntaxHighlighter
          language={language ? language : "text"}
          style={twilight}
        >
          {code}
        </SyntaxHighlighter>
      )}
    </div>
  );
};

export default MarkdownRenderer;
