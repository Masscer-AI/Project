import React, { useState } from "react";
import { useTranslation } from "react-i18next";
import { generateImage } from "../../modules/apiCalls";
import toast from "react-hot-toast";
import {
  Modal,
  Button,
  Textarea,
  NativeSelect,
  Stack,
  Text,
  Group,
} from "@mantine/core";
import { IconSparkles } from "@tabler/icons-react";

const FLUX_SIZES = [
  "512x512", // 1:1
  "1024x1024", // 1:1
  "1440x1440", // 1:1
  "1440x768", //
  "1024x768",
  "1280x768",
  "768x1440",
  "1280x1024",
  "1024x1280",
  "1280x1440",
  "1440x1280",
];

const ULTRA_FLUX_SIZES = ["1x1", "16x9", "4x3", "21x9", "9x21", "3x4", "9x16"];

const modelSizes = {
  "dall-e-2": ["256x256", "512x512", "1024x1024"],
  "dall-e-3": ["1024x1024", "1792x1024", "1024x1792"],
  "flux-pro-1.1-ultra": [...ULTRA_FLUX_SIZES],
  "flux-pro-1.1": [...FLUX_SIZES],
  "flux-pro": [...FLUX_SIZES],
  "flux-dev": [...FLUX_SIZES],
};

export const ImageGenerator = ({
  messageId,
  initialPrompt,
  hide,
  onResult,
}: {
  messageId: number;
  initialPrompt: string;
  hide: () => void;
  onResult: (imageUrl: string, imageContentB64: string) => void;
}) => {
  const [prompt, setPrompt] = useState(initialPrompt);
  const [model, setModel] = useState("flux-pro-1.1");
  const [size, setSize] = useState("768x1440");

  const { t } = useTranslation();

  const handleModelChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setModel(event.target.value);
    setSize(modelSizes[event.target.value][0]);
  };

  const generate = async () => {
    hide();
    const tid = toast.loading(t("generating-image"));
    try {
      const { image_url, image_content_b64, image_name } = await generateImage(
        prompt,
        messageId,
        size,
        model
      );
      toast.dismiss(tid);
      toast.success(t("image-generated"));
      onResult(image_content_b64, image_name);
    } catch (error) {
      console.error("Error generating image:", error);
      toast.dismiss(tid);
      toast.error(t("error-generating-image") + error.response.data.error);
    }
  };

  return (
    <Modal opened={true} onClose={hide} title="Image generator" size="lg" centered>
      <Stack gap="md">
        <NativeSelect
          label={t("choose-model")}
          value={model}
          onChange={(e) => {
            const val = e.currentTarget.value;
            setModel(val);
            setSize(modelSizes[val][0]);
          }}
          data={Object.keys(modelSizes)}
        />

        <Textarea
          label={t("prompt")}
          placeholder={t("write-detailed-prompt")}
          value={prompt}
          onChange={(e) => setPrompt(e.currentTarget.value)}
          autosize
          minRows={3}
        />

        <Text size="sm" fw={500}>{t("choose-aspect-ratio")}</Text>
        <div className="d-flex wrap-wrap justify-center">
          {modelSizes[model].map((s) => (
            <AspectRatio
              key={s}
              onClick={() => setSize(s)}
              size={s}
              selected={size === s}
            />
          ))}
        </div>

        <Button
          fullWidth
          leftSection={<IconSparkles size={18} />}
          onClick={generate}
        >
          Generate
        </Button>
      </Stack>
    </Modal>
  );
};

export const AspectRatio = ({
  size,
  separator = "x",
  selected = false,
  onClick = () => {},
}) => {
  const [width, height] = size.split(separator).map(Number);
  const relation = height / width;

  const minWidth = 100;
  let calculatedHeight = minWidth * relation;
  return (
    <div
      className={`pointer d-flex align-center justify-center flex-y ${selected ? "bg-active" : "bg-hovered"}`}
      style={{
        width: `${minWidth}px`,
        height: `${calculatedHeight}px`,
        border: "1px solid black",
        margin: "5px",
      }}
      onClick={onClick}
    >
      <span>
        {width}
        {separator}
        {height}
      </span>
    </div>
  );
};

const DynamicAspectRatio = ({
  selected = false,
  onChange = (size: string) => {},
}) => {
  const [width, setWidth] = useState(1); // Start with a default width
  const [height, setHeight] = useState(1); // Start with a default height

  const handleWidthChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newWidth = Number(event.target.value);
    setWidth(newWidth);
    onChange(`${newWidth}:${height}`); // Update the aspect ratio format
  };

  const handleHeightChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const newHeight = Number(event.target.value);
    setHeight(newHeight);
    onChange(`${width}:${newHeight}`); // Update the aspect ratio format
  };

  return (
    <div
      className={`d-flex align-center justify-center flex-y ${selected ? "bg-active" : "bg-hovered"}`}
    >
      <div style={{ margin: "10px" }}>
        <label>
          Width: {width}
          <input
            type="range"
            min="1"
            max="16" // You can configure the maximum value as needed
            value={width}
            onChange={handleWidthChange}
            style={{ width: "150px" }}
          />
        </label>
      </div>
      <div style={{ margin: "10px" }}>
        <label>
          Height: {height}
          <input
            type="range"
            min="1"
            max="16" // You can configure the maximum value as needed
            value={height}
            onChange={handleHeightChange}
            style={{ width: "150px" }}
          />
        </label>
      </div>
      <div>
        Aspect Ratio: {width}:{height}
      </div>
    </div>
  );
};
