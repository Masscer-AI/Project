import React from "react";

export const Checkbox = ({
  checked,
  onChange,
  checkedFill = "var(--active-color)",
  unCheckedFill = "var(--hovered-color)",
}) => {
  return (
    <input
      className="checkbox"
      type="checkbox"
      style={{
        backgroundColor: checked ? checkedFill : unCheckedFill,
      }}
      checked={checked}
      onChange={onChange}
    />
  );
};
