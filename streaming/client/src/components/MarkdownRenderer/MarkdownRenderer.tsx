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

const MarkdownRenderer = ({
  markdown,
  extraClass,
}: {
  markdown: string;
  extraClass?: string;
}) => {
  const { t } = useTranslation();

  // const urlTransform = (url: string) => {
  //   return url;
  // };

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
            />
          );
        },
      }}
    >
      {markdown}
    </Markdown>
  );
};

const output_formats = ["docx", "pdf", "md", "csv", "html", "json", "txt"];
type TOutputFormat = "docx" | "pdf" | "md" | "csv" | "html" | "json" | "txt";

const text_only_formats = ["csv", "txt", "json"];

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

export const CustomCodeBlock = ({ code, language }) => {
  const { t } = useTranslation();
  const [output_format, setOutputFormat] = useState<TOutputFormat>("docx");
  const [input_format, setInputFormat] = useState("md");

  useEffect(() => {
    // If the language is HTML, set the output format to HTML
    if (language === "html") {
      setInputFormat("html");
    }
  }, []);

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

  return (
    <div className="code-block">
      <div className="actions flex-x align-center justify-between bg-hovered rounded">
        <section className="flex-x gap-small align-center">
          <Pill>{language ? language : "text"}</Pill>
        </section>
        <section className="flex-x align-center">
          <SvgButton
            extraClass="pressable active-on-hover "
            text={t("copy")}
            onClick={handleCopy}
          />
          <div className="flex-x active-on-hover  rounded">
            <SvgButton
              extraClass="pressable "
              text={t("export-to")}
              onClick={handleTransform}
            />
            <select
              className="rounded  input"
              value={output_format}
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
      <SyntaxHighlighter
        language={language ? language : "text"}
        style={twilight}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
};

export default MarkdownRenderer;
