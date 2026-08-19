import React from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Anchor } from "@mantine/core";

type Props = {
  markdown: string;
  className?: string;
};

export function LegalMarkdown({ markdown, className }: Props) {
  return (
    <div className={className ?? "legal-markdown"}>
      <Markdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ href, children }) => (
            <Anchor href={href} target="_blank" rel="noopener noreferrer" size="sm">
              {children}
            </Anchor>
          ),
        }}
      >
        {markdown}
      </Markdown>
    </div>
  );
}
