import React from "react";
import { Calculator } from "../components/MessagePlugins/Calculator/Calculator";
import { CodeBlock } from "../components/CodeBlock/CodeBlock";

const calculatorInstructions = `
### Documentation: JSON Structure for the "Calculator" Plugin

The "calculator" plugin processes a sequence of mathematical operations based on a predefined JSON structure. This document outlines the required structure and rules for defining a valid JSON input to use with the plugin.

---

### JSON Structure Overview

The JSON must contain a list of operations, where each operation adheres to the following structure:

\`\`\`json
{
  "plugin": "calculator",
  "operations": [
    { 
      "name": "operation_name",
      "arguments": ["arg1", "arg2", ...],
      "result_name": "result_identifier",
      "label": "description_of_operation",
      "result_value": null
    }
  ]
}
\`\`\`

---

### Fields Description

1. **plugin** (string):
   - **Required**: Yes
   - **Description**: Identifies the plugin. Must always be set to \`"calculator"\`.
   - **Example**: \`"plugin": "calculator"\`

2. **operations** (array):
   - **Required**: Yes
   - **Description**: A list of operations to be executed in sequence. Each operation must follow the structure below.

#### Operation Object Fields

Each operation object within the \`operations\` array must include the following fields:

1. **name** (string):
   - **Required**: Yes
   - **Description**: The name of the operation to be performed. Must be one of the following:
     - \`"sum"\`: Adds multiple numbers.
     - \`"rest"\`: Subtracts numbers sequentially.
     - \`"multiply"\`: Multiplies multiple numbers.
     - \`"divide"\`: Divides two numbers.
     - \`"sqrt"\`: Calculates the square root of a number.
     - \`"floor"\`: Rounds a number down to the nearest integer.
     - \`"power"\`: Raises a number to the power of another.
     - \`"mod"\`: Calculates the remainder of a division.
     - \`"ceil"\`: Rounds a number up to the nearest integer.
     - \`"round"\`: Rounds a number to the nearest integer.
     - \`"abs"\`: Returns the absolute value of a number.
     - \`"factorial"\`: Calculates the factorial of a number (non-negative integers only).
     - \`"exponential"\`: Calculates $e^x$.
     - \`"percentage"\`: Computes the percentage of one number relative to another.
   - **Example**: \`"name": "sum"\`

2. **arguments** (array):
   - **Required**: Yes  
   - **Description**: A list of arguments for the operation. Arguments can be either:
     - A **number** (e.g., \`5\`, \`3.14\`).
     - A **string** referencing the result of a previous operation (e.g., \`"result1"\`).
   - **Rules**:
     - For unary operations (e.g., \`"sqrt"\`,\`"abs"\`), the array must contain exactly **1 argument**.
     - For binary operations (e.g., \`"divide"\`,\`"power"\`,\`"mod"\`,\`"percentage"\`), the array must contain exactly **2 arguments**.
     - For operations like \`"sum"\` or \`"multiply"\`,\` the array can contain **2 or more arguments**.
   - **Example**: \`"arguments": [5, 3]\` or \`"arguments": ["result1", 2]\`

3. **result_name** (string):
   - **Required**: Yes
   - **Description**: A unique identifier for storing the result of this operation. This identifier can be referenced as an argument in subsequent operations.
   - **Example**: \`"result_name": "result1"\`

4. **label** (string):
   - **Required**: Yes
   - **Description**: A human-readable description of the operation for logging or debugging purposes.
   - **Example**: \`"label": "Sum of 5 and 3"\`

5. **result_value** (number or null):
   - **Required**: Yes
   - **Description**: Initially set to \`null\`. After processing, it will be populated with the result of the operation.
   - **Example**: \`"result_value": null\`

---

### Example JSON Input

Here is a complete example JSON input for the "calculator" plugin:

\`\`\`json
{
  "plugin": "calculator",
  "operations": [
    {
      "name": "sum",
      "arguments": [5, 3],
      "result_name": "result1",
      "label": "Sum of 5 and 3",
      "result_value": null
    },
    {
      "name": "multiply",
      "arguments": ["result1", 2],
      "result_name": "result2",
      "label": "Multiplication of result1 by 2",
      "result_value": null
    },
    {
      "name": "sqrt",
      "arguments": ["result2"],
      "result_name": "result3",
      "label": "Square root of result2",
      "result_value": null
    },
    {
      "name": "percentage",
      "arguments": ["result3", 100],
      "result_name": "result4",
      "label": "Percentage of result3 over 100",
      "result_value": null
    }
  ]
}
\`\`\`



### Execution Rules

1. **Sequential Execution**:
   - Operations are executed in the order they are defined in the \`operations\` array.
   - If an operation references a \`result_name\` that has not been computed yet, the plugin will throw an error.

2. **Error Handling**:
   - If an unsupported operation is provided, the plugin will throw an error with the message: \`Unsupported operation: <operation_name>\`.
   - If the number of arguments does not match the requirements of the operation, the plugin will throw an error with the message: \`Invalid number of arguments for operation: <operation_name>\`.

3. **Circular Dependencies**:
   - Circular dependencies (e.g., \`result1\` depends on \`result2\`, and \`result2\` depends on \`result1\`) are not supported and will cause the plugin to fail.

---

### Notes and Best Practices

1. **Unique \`result_name\`**:
   - Ensure that each \`result_name\` is unique within the JSON to avoid overwriting results.

2. **Referencing Results**:
   - When referencing a previous result in \`arguments\`, make sure the referenced \`result_name\` has already been computed.

3. **Validation**:
   - Double-check the number of arguments for each operation to ensure they match the requirements.

4. **Factorial Limitations**:
   - The \`factorial\` operation only supports non-negative integers. Passing a negative number will throw an error.
`;

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
  calculator: {
    name: "Calculator",
    slug: "calculator",
    codeKey: "calculator",
    instructions: calculatorInstructions,
    descriptionTranslationKey: "calculator-description",
    code_receptor: (code: string, language: string) => {
      return <Calculator {...JSON.parse(code)} />;
    },
    // icon: <CalculatorIcon />,
  },
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
