import React, { useEffect, useCallback } from "react";
import MarkdownIt from "markdown-it";
import hljs from "highlight.js/lib/common";

import "highlight.js/styles/tokyo-night-dark.css";
import toast from "react-hot-toast";
import "./MarkdownRenderer.css";
import { debounce } from "../../modules/utils";
import { downloadFile, generateDocument } from "../../modules/apiCalls";
import { useTranslation } from "react-i18next";

const DEBOUNCE_TIME = 180;

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
});

const MarkdownRenderer = ({
  markdown,
  extraClass,
}: {
  markdown: string;
  extraClass?: string;
}) => {
  const { t } = useTranslation();

  const highlightCodeBlocks = useCallback(
    debounce(() => {
      document.querySelectorAll("pre code").forEach((block) => {
        const htmlBlock = block as HTMLElement;
        if (!htmlBlock.dataset.highlighted) {
          hljs.highlightElement(htmlBlock);
          htmlBlock.dataset.highlighted = "true";
        }
      });
    }, DEBOUNCE_TIME),
    []
  );

  const addCopyButtons = useCallback(
    debounce(() => {
      document.querySelectorAll("pre").forEach((block) => {
        if (!block.querySelector(".copy-btn")) {
          // Create a div to hold the buttons
          const buttonContainer = document.createElement("div");
          buttonContainer.className = "d-flex gap-small align-center copy-btn";

          // Create the Copy button
          const button = document.createElement("button");
          button.className =
            " clickeable rounded padding-small bg-hovered active-on-hover";
          button.textContent = t("copy");

          // Create the Transform button
          const transformButton = document.createElement("button");
          transformButton.className =
            "clickeable rounded padding-small bg-hovered active-on-hover";
          transformButton.textContent = t("transform-to-docx");

          // Append buttons to the container
          buttonContainer.appendChild(button);
          buttonContainer.appendChild(transformButton);

          // Append the container to the block
          block.appendChild(buttonContainer);

          // Copy button event listener
          button.addEventListener("click", () => {
            const codeElement = block.querySelector("code");
            const code = codeElement ? codeElement.textContent : "";

            if (code) {
              navigator.clipboard.writeText(code);
              toast.success("Code copied to clipboard!");
            } else {
              toast.error("No code available!");
            }
          });

          // Transform button event listener
          transformButton.addEventListener("click", async () => {
            let input_format = "md";
            const codeElement = block.querySelector("code");
            const code = codeElement ? codeElement.textContent : "";
            // get the classlist of the code block
            const codeBlockClassList = codeElement?.classList;
            // check if the code block is a language-html
            if (codeBlockClassList?.contains("language-html")) {
              input_format = "html";
            }

            if (code) {
              const tid = toast.loading(t("generating-document"));
              try {
                const res = await generateDocument({
                  source_text: code,
                  from_type: input_format,
                  to_type: "docx",
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
          });
        }
      });
    }, DEBOUNCE_TIME),
    []
  );

  useEffect(() => {
    highlightCodeBlocks();
    addCopyButtons();
  }, [markdown]);

  const getMarkdownText = () => {
    const rawMarkup = md.render(markdown);
    return { __html: rawMarkup };
  };

  return (
    <div
      className={`markdown-renderer ${extraClass}`}
      dangerouslySetInnerHTML={getMarkdownText()}
    />
  );
};

export default MarkdownRenderer;
