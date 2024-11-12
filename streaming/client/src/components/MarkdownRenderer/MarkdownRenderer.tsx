import React, { useEffect, useCallback } from "react";
import MarkdownIt from "markdown-it";
import hljs from "highlight.js/lib/common";

import "highlight.js/styles/tokyo-night-dark.css";
import toast from "react-hot-toast";
import "./MarkdownRenderer.css";
import { debounce } from "../../modules/utils";
import { downloadFile, generateDocument } from "../../modules/apiCalls";

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
          button.className = " clickeable rounded padding-small bg-hovered";
          button.textContent = "Copy";

          // Create the Transform button
          const transformButton = document.createElement("button");
          transformButton.className =
            "clickeable rounded padding-small bg-hovered";
          transformButton.textContent = "Transform";

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
            const codeElement = block.querySelector("code");
            const code = codeElement ? codeElement.textContent : "";

            if (code) {
              const res = await generateDocument({
                source_text: code,
                from_type: "html",
                to_type: "docx",
              });

              console.log(res);
              // @ts-ignore
              console.log(res.output_filepath);
              
// @ts-ignore
              await downloadFile(res.output_filepath);

              // navigator.clipboard.writeText(code);
              toast.success("Document being generated");
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
