import React from "react";

export const SliderInput = ({
  checked,
  onChange,
  labelTrue = "Yes",
  labelFalse = "No",
  extraClass = "",
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  labelTrue?: string;
  labelFalse?: string;
  extraClass?: string;
}) => {
  return (
    <div className={`d-flex gap-medium ${extraClass}`}>
      <label className="switch">
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className="slider"></span>
      </label>
      <span>{checked ? labelTrue : labelFalse}</span>
    </div>
  );
};
