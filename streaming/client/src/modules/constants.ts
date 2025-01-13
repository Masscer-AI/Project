export const API_URL =
  // @ts-ignore
  import.meta.env.VITE_API_URL || "http://localhost:8000";
export const STREAMING_BACKEND_URL =
  window.location.origin === "http://localhost:5173"
    ? "http://localhost:8001"
    : window.location.origin;

export const PUBLIC_TOKEN =
  // @ts-ignore
  import.meta.env.VITE_PUBLIC_TOKEN || "39ece367b84b4bd19622692cc70361f2";

export function getRandomWordsAndSlug() {
  const randomWords = [
    "apple",
    "banana",
    "cherry",
    "date",
    "elderberry",
    "fig",
    "grape",
    "honeydew",
    "kiwi",
    "lemon",
    "mango",
    "nectarine",
    "orange",
    "papaya",
    "quince",
    "raspberry",
    "strawberry",
    "tangerine",
    "ugli",
    "vanilla",
    "watermelon",
    "xigua",
    "yam",
    "zucchini",
    "avocado",
    "blueberry",
    "cantaloupe",
    "dragonfruit",
    "eggplant",
    "fennel",
    "guava",
    "huckleberry",
    "jackfruit",
    "kumquat",
    "lime",
    "mulberry",
    "olive",
    "peach",
    "plum",
    "starfruit",
  ];

  const selectedWords = randomWords.sort(() => 0.5 - Math.random()).slice(0, 3);

  const slug = selectedWords.join("-").toLowerCase();

  return {
    name: selectedWords.join(" "),
    slug: slug,
  };
}

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

export const SYSTEM_PLUGINS = [
  {
    name: "Calculator",
    slug: "calculator",
    instructions: calculatorInstructions,
    descriptionTranslationKey: "calculator-description",
    // icon: <CalculatorIcon />,
  },
  {
    name: "Mermaid Diagrams",
    slug: "mermaid-diagrams",
    descriptionTranslationKey: "mermaid-diagrams-description",
    instructions: mermaidInstructions,
  },
];
