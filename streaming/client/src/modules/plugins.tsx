import React from "react";
import { CodeBlock } from "../components/CodeBlock/CodeBlock";

const mermaidInstructions = `
To use mermaid, you must provide a markdown code block with valid MermaidJS syntax.

For example:

\`\`\`mermaid
graph TD
    A[Inicio] --> B[Evaluar idea]
    B -->|Idea viable| C[Planificar proyecto]
    B -->|Idea no viable| D[Descartar idea]
    C --> E[Desarrollo]
    E --> F[Testeo]
    F -->|Pruebas exitosas| G[Implementación]
    F -->|Pruebas fallidas| E
    G --> H[Fin]
\`\`\`

## RULES:

- Never add parenthesis inside [ ] because it will break the mermaid syntax and throw an error, use a different approach instead of parenthesis.
- This is an example ERROR:
\`\`\`mermaid
graph TD
    A[Inicio] --> B[Reunir ingredientes]
    B --> C[Preparar arroz (100g)]
\`\`\`

In the second line, the parenthesis will break the mermaid syntax and throw an error, so, NEVER add parenthesis inside [ ].
`;

const documentMakerInstructions = `
### Main Task
Your main task will be writing engaging and accurate documents in **Markdown** or **HTML** format. Deliver the code for the documents inside code blocks using triple backticks.

---

### Examples

#### Example 1: HTML Document  
The initial comment is mandatory.

<!-- DOCUMENT_FROM_HTML -->
\`\`\`html
<!DOCTYPE html>
<html>
<head>
    <title>The Title of the Document</title>
    <meta name="author" content="Your Name">
    <meta name="description" content="Some description of the document">
    <meta name="date" content="2024-11-14">
    <style>
        body { font-family: Arial, sans-serif; }
        h1 { color: #333; }
        p { line-height: 1.6; }
    </style>
</head>
<body>
    <p>This is an example of HTML content for the document.</p>
</body>
</html>
\`\`\`

#### Example 2: Markdown Document  
The initial comment is mandatory.

<!-- DOCUMENT_FROM_MD -->
\`\`\`
---
title: "The Title of the Document"
author: "Your Name"
description: "Some description of the document"
date: "2024-11-14"
---
This is an example of Markdown content for the document.

... More markdown content
\`\`\`

---

### Important Notes

1. **Provide Relevant Metadata**:  
   Ensure the following metadata fields are included:
   - **title**: The main title of the document, which will appear at the top center of the document. (No need to add it again in the body.)
   - **author**: The name of the document's creator.
   - **description**: A concise summary of the document's content.
   - **date**: The creation or publication date of the document.

2. **Use Tables for Layouts**:  
   For layouts, incorporate tables creatively to enrich the document's structure.

3. **Pandoc Compatibility**:  
   The documents will be converted using **Pandoc**, transforming them into DOCX or PDF formats. Ensure your documents are formatted to be compatible with Pandoc's parsing capabilities.

---

### Special Instructions
- Return your response only in **HTML** documents.
- Answer **only** with the document in the specified format.
`;

type TPlugin = {
  name: string;
  slug: string;
  codeKey: string;
  instructions: string;
  descriptionTranslationKey: string;
  code_receptor?: (code: string, language: string) => React.ReactNode;
};

const RenderHTML = ({ htmlContent }) => {
  return <div dangerouslySetInnerHTML={{ __html: htmlContent }} />;
};

export const SYSTEM_PLUGINS: Record<string, TPlugin> = {
  mermaid: {
    name: "Mermaid Diagrams",
    slug: "mermaid-diagrams",
    codeKey: "mermaid",
    descriptionTranslationKey: "mermaid-diagrams-description",
    instructions: mermaidInstructions,
    code_receptor: (code: string, language: string) => {
      return <CodeBlock code={code} language="mermaid" />;
    },
  },
  documentMaker: {
    name: "Document Maker",
    codeKey: "documentMaker",
    slug: "document-maker",
    descriptionTranslationKey: "document-maker-description",
    instructions: documentMakerInstructions,
    code_receptor: (code: string, language: string) => {
      return <RenderHTML htmlContent={code} />;
    },
  },
};
