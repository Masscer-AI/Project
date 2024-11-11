import React from "react";

export const SliderInput = ({
  checked,
  onChange,
  labelTrue = "Yes",
  labelFalse = "No",
  extraClass = "",
  keepActive = false,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  labelTrue?: string;
  labelFalse?: string;
  extraClass?: string;
  keepActive?: boolean;
}) => {
  return (
    <div className={`d-flex gap-medium ${extraClass} `}>
      <label className={`switch `}>
        <input
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
        />
        <span className={`slider ${keepActive && "keep-active"}`}></span>
      </label>
      <span>{checked ? labelTrue : labelFalse}</span>
    </div>
  );
};
