import React, { useState } from "react";
import { Textarea } from "../SimpleForm/Textarea";
import { Modal } from "../Modal/Modal";
import toast from "react-hot-toast";

export const ImageGenerator = ({
  initialPrompt,
  hide 
}: {
  initialPrompt: string;
  hide : () => void;
}) => {
  const [prompt, setPrompt] = useState(initialPrompt.slice(0, 500));

  return (
    <Modal
      hide={hide}
    >
      <div className="d-flex flex-y gap-big">
        <h1 className="fancy-bg padding-medium text-center">Image Generator</h1>
        <h4 className="text-center">Choose aspect ratio</h4>
        <Textarea
          onChange={(value: string) => setPrompt(value)}
          placeholder="Write a good prompt"
          defaultValue={prompt}
        />
      </div>
    </Modal>
  );
};
