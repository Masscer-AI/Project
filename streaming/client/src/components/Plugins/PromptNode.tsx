import React, { useEffect, useState, useCallback } from "react";
import { NodeProps, Node } from "@xyflow/react";

import { NodeTemplate } from "./NodeTemplate";
import { promptNodeAction } from "../../modules/apiCalls";
import { SvgButton } from "../SvgButton/SvgButton";
import toast from "react-hot-toast";
import MarkdownRenderer from "../MarkdownRenderer/MarkdownRenderer";
import { AgentSelector } from "../AgentSelector/AgentSelector";
import { useStore } from "../../modules/store";
import { useTranslation } from "react-i18next";
import { SliderInput } from "../SimpleForm/SliderInput";
import { Textarea } from "../SimpleForm/Textarea";
import { Select } from "../SimpleForm/Select";
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

const DEFAULT_OUTPUT_FOR_TESTING =
  "Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos. Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos. Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos.  Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos. Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos. Lorem ipsum dolor sit amet consectetur adipisicing elit. Quisquam, quos.  ";

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
        <h2>Text Node</h2>
        <Textarea
          defaultValue={systemPrompt}
          onChange={(value) => setSystemPrompt(value)}
          placeholder="System prompt"
        />
        <Textarea
          defaultValue={userMessage}
          onChange={(value) => setUserMessage(value)}
          placeholder="User message"
        />

        <Select
          placeholder={t("model")}
          options={models.map((m) => m.slug)}
          value={model}
          onChange={(value) => setModel(value)}
        />

        {/* <AgentSelector /> */}
        {output && (
          <>
            <h3>Output</h3>
            <div
              style={{ maxHeight: "300px", overflow: "scroll" }}
              className="padding-small bg-secondary rounded nodrag nowheel"
            >
              <MarkdownRenderer markdown={output} />
            </div>
          </>
        )}
        <SvgButton
          text={"Test node"}
          extraClass="bg-secondary"
          onClick={test}
        />
        <SliderInput
          labelFalse="JSON"
          labelTrue="Text"
          checked={outputType === "text"}
          onChange={(checked) => setOutputType(checked ? "text" : "json")}
        />
        {outputType === "json" && <textarea className="textarea" />}
      </div>
    </NodeTemplate>
  );
};
