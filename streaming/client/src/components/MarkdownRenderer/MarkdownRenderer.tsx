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
import { SvgButton } from "../SvgButton/SvgButton";
import { Pill } from "../Pill/Pill";

import { Calculator } from "../MessagePlugins/Calculator/Calculator";
import { CodeBlock } from "../CodeBlock/CodeBlock";
import { SYSTEM_PLUGINS } from "../../modules/plugins";

const MarkdownRenderer = ({
  markdown,
  extraClass,
  onChange,
}: {
  markdown: string;
  extraClass?: string;
  onChange?: (markdown: string) => void;
}) => {
  const { t } = useTranslation();

  // const urlTransform = (url: string) => {
  //   return url;
  // };

  const changeInMarkdown = (search: string, replace: string) => {
    const newMarkdown = markdown.replace(search, replace);
    if (onChange) {
      onChange(newMarkdown);
    }
  };

  return (
    <Markdown
      className={`markdown-renderer ${extraClass}`}
      // urlTransform={urlTransform}
      remarkPlugins={[
        [remarkGfm, { singleTilde: false }],
        [remarkMath],
        // [docx, { output: "blob" }],
      ]}
      rehypePlugins={[rehypeKatex]}
      skipHtml={true}
      components={{
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

    if (language === "json") {
      findPlugin();
    }

    if (language === "documentMaker") {
      setPluginName("documentMaker");
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
      <div className="actions flex-x align-center justify-between bg-hovered rounded">
        <section className="flex-x gap-small align-center">
          <Pill>
            {label?.slice(0, 1).toUpperCase() + (label ? label.slice(1) : "")}
          </Pill>
        </section>
        <section className="flex-x align-center wrap-wrap gap-small padding-small justify-end">
          <SvgButton
            extraClass="pressable active-on-hover bg-hovered"
            text={t("copy")}
            onClick={handleCopy}
          />
          {pluginName && (
            <SvgButton
              extraClass="pressable active-on-hover bg-hovered"
              text={
                usePlugin
                  ? t("view-code")
                  : t("use-plugin") + ": " + t(pluginName)
              }
              onClick={
                usePlugin
                  ? () => setUsePlugin(false)
                  : () => {
                      setUsePlugin(true);
                    }
              }
            />
          )}
          <div className="flex-x active-on-hover  bg-hovered rounded">
            <SvgButton
              extraClass="pressable "
              text={t("export-to")}
              onClick={handleTransform}
            />
            <select
              className="rounded  input"
              value={output_format}
              name="output-format"
              onChange={(e) => setOutputFormat(e.target.value as TOutputFormat)}
            >
              {output_formats.map((format) => (
                <option key={format} value={format}>
                  {format.toUpperCase()}
                </option>
              ))}
            </select>
          </div>
        </section>
      </div>

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
