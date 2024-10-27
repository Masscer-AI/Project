import React from "react";
import "./SvgButton.css";

export const SvgButton = ({
  svg,
  text = "",
  onClick = () => {},
  extraClass = "",
  size = "small",
}) => {
  return (
    <button
      tabIndex={0}
      className={`svg-button clickeable ${extraClass} ${size}`}
      onClick={onClick}
    >
      <span>{svg}</span>
      <span>{text}</span>
    </button>
  );
};
