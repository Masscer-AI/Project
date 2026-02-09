import React, { useEffect, useState, useCallback } from "react";
import { NodeProps, Node } from "@xyflow/react";

import { NodeTemplate } from "./NodeTemplate";
import { promptNodeAction } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";

import {
  Button,
  NativeSelect,
  SegmentedControl,
  Textarea,
  Text,
  ScrollArea,
} from "@mantine/core";
import { IconPlayerPlay } from "@tabler/icons-react";

export type TPromptNode = Node<
  {
    url?: string;
    onDelete: () => void;
    onChange: (newLabel: string) => void;
    onFinish: (output: any) => void;
    isActive: boolean;
    inputs: any;
  },
  "websiteReaderNode"
>;

export const PromptNode = ({ data }: NodeProps<TPromptNode>) => {
  const [systemPrompt, setSystemPrompt] = useState(
    "You are an useful assistant"
  );
  const [userMessage, setUserMessage] = useState("");
  const [model, setModel] = useState("gpt-4o-mini");
  const [inputType, setInputType] = useState<"text" | "json" | null>(null);
  const [shouldRun, setShouldRun] = useState(false);
  const [output, setOutput] = useState("");
  const [outputType, setOutputType] = useState<"text" | "json">("text");

  const { agents, models } = useStore((state) => ({
    agents: state.agents,
    models: state.models,
  }));

  const { t } = useTranslation();

  const processInputs = useCallback(() => {
    if (typeof data.inputs === "string") {
      setInputType("text");
      setUserMessage(data.inputs);
      setShouldRun(true);
    } else if (typeof data.inputs === "object") {
      setInputType("json");
    }
  }, [data.inputs]);

  const test = useCallback(async () => {
    try {
      const res = await promptNodeAction({
        system_prompt: systemPrompt,
        model: model,
        user_message: userMessage,
        response_format: "text",
      });
      setOutput(res.response);
      data.onFinish(res.response);
    } catch (e) {
      toast.error("Test failed");
    }
  }, [systemPrompt, userMessage, model]);

  useEffect(() => {
    if (data.isActive) {
      processInputs();
    }
  }, [data.isActive]);

  useEffect(() => {
    if (shouldRun) {
      test();
    }
  }, [shouldRun]);

  return (
    <NodeTemplate data={data} bgColor="var(--hovered-color)">
      <div className="d-flex flex-y gap-big">
        <Text fw={600} size="lg">
          Text Node
        </Text>
        <Textarea
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.currentTarget.value)}
          placeholder="System prompt"
          autosize
          minRows={2}
          maxRows={5}
        />
        <Textarea
          value={userMessage}
          onChange={(e) => setUserMessage(e.currentTarget.value)}
          placeholder="User message"
          autosize
          minRows={2}
          maxRows={5}
        />

        <NativeSelect
          value={model}
          onChange={(e) => setModel(e.currentTarget.value)}
          data={models.map((m) => ({ value: m.slug, label: m.slug }))}
        />

        {output && (
          <>
            <Text fw={500} size="sm">
              Output
            </Text>
            <ScrollArea.Autosize
              mah={300}
              className="nodrag nowheel"
              style={{
                background: "var(--bg-secondary-color)",
                borderRadius: "var(--standard-radius)",
                padding: 8,
              }}
            >
              <MarkdownRenderer markdown={output} />
            </ScrollArea.Autosize>
          </>
        )}

        <Button
          leftSection={<IconPlayerPlay size={16} />}
          onClick={test}
          size="xs"
        >
          Test node
        </Button>

        <SegmentedControl
          value={outputType}
          onChange={(val) => setOutputType(val as "text" | "json")}
          data={[
            { value: "text", label: "Text" },
            { value: "json", label: "JSON" },
          ]}
          size="xs"
        />
        {outputType === "json" && (
          <Textarea placeholder="JSON schema" autosize minRows={2} />
        )}
      </div>
    </NodeTemplate>
  );
};
