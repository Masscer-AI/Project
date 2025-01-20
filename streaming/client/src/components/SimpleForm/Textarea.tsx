import React, { useEffect, useRef } from "react";
import { Pill } from "../Pill/Pill";

export const Textarea = ({
  defaultValue = "",
  onChange,
  placeholder = "",
  label = "",
  extraClass = "",
  maxLength,
  name = "",
}: {
  defaultValue?: string;
  onChange?: (value: string) => void;
  placeholder?: string;
  label?: string;
  extraClass?: string;
  maxLength?: number;
  name?: string;
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
      <span className="above-all rounded">{label}</span>
      <textarea
        name={name}
        ref={textareaRef}
        className="textarea"
        maxLength={maxLength}
        defaultValue={defaultValue}
        onChange={(e) => {
          onChange && onChange(e.target.value);
        }}
        placeholder={placeholder}
      />
    </div>
  );
};
