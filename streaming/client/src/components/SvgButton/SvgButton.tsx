import React from "react";
import "./SvgButton.css";

export const SvgButton = ({ text = "", svg, onClick, extraClass = "" }) => {
  return (
    <div tabIndex={0} className={`svg-button clickeable ${extraClass}`} onClick={onClick}>
      <button tabIndex={-1}>
        {svg} {text}
      </button>
    </div>
  );
};
