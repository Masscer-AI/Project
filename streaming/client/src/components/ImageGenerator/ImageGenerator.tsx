import React, { useState } from "react";
import { Textarea } from "../SimpleForm/Textarea";
import { Modal } from "../Modal/Modal";
import { SvgButton } from "../SvgButton/SvgButton";
import { useTranslation } from "react-i18next";
import { generateImage } from "../../modules/apiCalls";
import { SVGS } from "../../assets/svgs";
import toast from "react-hot-toast";

const FLUX_SIZES = [
  "512x512",
  "1024x1024",
  "1440x1440",
  "1440x768",
  "1024x768",
  "1280x768",
  // Other layouts
  "768x1024",
  "768x1440",
];


const modelSizes = {
  "dall-e-2": ["256x256", "512x512", "1024x1024"],
  "dall-e-3": ["1024x1024", "1792x1024", "1024x1792"],
  "flux-pro-1.1-ultra": [...FLUX_SIZES],
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
  onResult: (imageUrl: string) => void;
}) => {
  const [prompt, setPrompt] = useState(initialPrompt.slice(0, 500));
  const [model, setModel] = useState("dall-e-3");
  const [size, setSize] = useState(modelSizes[model][0]);

  const { t } = useTranslation();

  const handleModelChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    setModel(event.target.value);
    setSize(modelSizes[event.target.value][0]);
  };

  const generate = async () => {
    hide();
    const tid = toast.loading(t("generating-image"));
    try {
      const response = await generateImage(prompt, messageId, size, model);
      toast.dismiss(tid);
      const imageUrl = response.image_url;
      toast.success(t("image-generated"));
      onResult(imageUrl);
    } catch (error) {
      console.error("Error generating image:", error);
      toast.dismiss(tid);
      toast.error(t("error-generating-image") + error.response.data.error);
    }
  };

  return (
    <Modal hide={hide}>
      <div className="d-flex flex-y gap-big">
        <h2 className=" padding-medium text-center">Image generator</h2>

        <div className="d-flex gap-big">
          <strong>Choose model</strong>
          <select
            className="rounded"
            onChange={handleModelChange}
            value={model}
          >
            {Object.keys(modelSizes).map((model) => (
              <option key={model} value={model}>
                {model}
              </option>
            ))}
          </select>
        </div>

        <strong>Prompt</strong>
        <Textarea
          onChange={(value: string) => setPrompt(value)}
          placeholder={t("write-detailed-prompt")}
          defaultValue={prompt}
        />

        <strong>Choose aspect ratio</strong>
        <div className="d-flex wrap-wrap justify-center">
          {modelSizes[model].map((s) => (
            <AspectRatio
              onClick={() => setSize(s)}
              size={s}
              selected={size === s}
            />
          ))}
        </div>
        <SvgButton
          svg={SVGS.stars}
          onClick={generate}
          extraClass="fancy-bg"
          size="big"
          text="Generate"
        />
      </div>
    </Modal>
  );
};
const AspectRatio = ({ size, selected = false, onClick = () => {} }) => {
  const [width, height] = size.split("x").map(Number);
  const relation = height / width;

  const minWidth = 150;
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
        {width}x{height}
      </span>
    </div>
  );
};
