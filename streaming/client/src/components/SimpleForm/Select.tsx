import React from "react";
import { Pill } from "../Pill/Pill";

export const Select = ({
  options,
  value,
  placeholder,
  onChange,
}: {
  options: string[];
  value: string;
  placeholder: string;
  onChange: (value: string) => void;
}) => {
  return (
    <div className="d-flex flex-y gap-small select-container">
      <Pill extraClass="bg-secondary">{placeholder}</Pill>
      <select className="rounded" value={value} onChange={(e) => onChange(e.target.value)}>
        {options.map((option) => (
          <option key={option} value={option}>
            {option}
          </option>
        ))}
      </select>
    </div>
  );
};
