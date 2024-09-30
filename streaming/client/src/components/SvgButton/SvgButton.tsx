import React from "react";
import "./SvgButton.css";

export const SvgButton = ({ text = "", svg, onClick, extraClass = "" }) => {
  return (
    <div className={`svg-button ${extraClass}`} onClick={onClick}>
      <button>
        {svg} {text}
      </button>
    </div>
  );
};
