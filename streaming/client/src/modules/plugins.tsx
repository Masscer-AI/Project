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

type TPlugin = {
  name: string;
  slug: string;
  codeKey: string;
  instructions: string;
  descriptionTranslationKey: string;
  code_receptor?: (code: string, language: string) => React.ReactNode;
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
};
