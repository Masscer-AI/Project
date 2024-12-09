import React, { useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
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
  style,
}: {
  markdown: string;
  extraClass?: string;
  style?: React.CSSProperties;
}) => {
  const { t } = useTranslation();

  const urlTransform = (url: string) => {
    return url;
  };

  return (
    <Markdown
      className={`markdown-renderer ${extraClass}`}
      urlTransform={urlTransform}
      remarkPlugins={[remarkGfm]}
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

const output_formats = ["docx", "pdf", "md"];

type TOutputFormat = "docx" | "pdf" | "md";

export const CustomCodeBlock = ({ code, language }) => {
  const { t } = useTranslation();
  const [output_format, setOutputFormat] = useState<TOutputFormat>("docx");
  const [input_format, setInputFormat] = useState("md");

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    toast.success(t("code-copied-to-clipboard"));
  };

  const handleTransform = async () => {
    if (code) {
      const tid = toast.loading(t("generating-document"));

      try {
        const res = await generateDocument({
          source_text: code,
          from_type: input_format,
          to_type: output_format,
        });
        // @ts-ignore
        await downloadFile(res.output_filepath);
        toast.dismiss(tid);
        toast.success(t("document-generated"));
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
      <div className="actions flex-x gap-small align-center justify-between">
        <section className="flex-x gap-small align-center">
          <SvgButton
            extraClass="pressable active-on-hover "
            text={t("copy")}
            onClick={handleCopy}
          />
          <div className="flex-x active-on-hover  rounded">
            <SvgButton
              extraClass="pressable "
              text={t("transform-to")}
              onClick={handleTransform}
            />
            <select
              className="rounded  "
              value={output_format}
              onChange={(e) => setOutputFormat(e.target.value as TOutputFormat)}
            >
              {output_formats.map((format) => (
                <option value={format}>{format.toUpperCase()}</option>
              ))}
            </select>
          </div>
        </section>
        <section className="flex-x gap-small align-center">
          <Pill>{language ? language : "text"}</Pill>
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
