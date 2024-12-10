import React from "react";
import DOMPurify from "dompurify";

export const HTMLRenderer = ({ html }: { html: string }) => {
  const clean = DOMPurify.sanitize(html);
  return <div dangerouslySetInnerHTML={{ __html: clean }}></div>;
};
