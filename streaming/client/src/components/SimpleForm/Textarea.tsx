import React, { useEffect, useRef } from "react";
import { Pill } from "../Pill/Pill";

export const Textarea = ({
  defaultValue,
  onChange,
  placeholder,
}: {
  defaultValue: string;
  onChange: (value: string) => void;
  placeholder: string;
}) => {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Function to resize the textarea
  const autoResize = () => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"; // Reset height
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`; // Set to scroll height
    }
  };

  useEffect(() => {
    autoResize(); // Resize on mount
  }, [defaultValue]); // Run when defaultValue changes

  return (
    <div className="d-flex flex-y gap-small textarea-container nowheel">
      <Pill>{placeholder}</Pill>
      <textarea
        ref={textareaRef}
        className="textarea"
        defaultValue={defaultValue}
        onChange={(e) => {
          onChange(e.target.value);
          autoResize();
        }}
        placeholder={""}
      />
    </div>
  );
};
