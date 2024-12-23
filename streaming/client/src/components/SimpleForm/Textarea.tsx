import React, { useEffect, useRef } from "react";
import { Pill } from "../Pill/Pill";

export const Textarea = ({
  defaultValue,
  onChange,
  placeholder,
  extraClass = "",
}: {
  defaultValue: string;
  onChange: (value: string) => void;
  placeholder: string;
  extraClass?: string;
}) => {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Function to resize the textarea
  const autoResize = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`;
    }
  };

  useEffect(() => {
    autoResize();
  }, [defaultValue]);

  return (
    <div
      className={` textarea-container nowheel max-height-500  ${extraClass}`}
    >
      <span className="above-all rounded">{placeholder}</span>
      <textarea
        ref={textareaRef}
        className="textarea"
        value={defaultValue}
        onChange={(e) => {
          onChange(e.target.value);
          // autoResize();
        }}
        placeholder={""}
      />
    </div>
  );
};
