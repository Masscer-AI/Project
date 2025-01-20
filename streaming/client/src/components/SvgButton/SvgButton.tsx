import React, { useState, useEffect, LegacyRef } from "react";
import "./SvgButton.css";

type SvgButtonProps = {
  svg?: React.ReactNode;
  text?: string;
  onClick?: () => void;
  extraClass?: string;
  size?: "small" | "big";
  confirmations?: string[];
  title?: string;
  reference?: LegacyRef<HTMLButtonElement>;
  tabIndex?: number;
  transparent?: boolean;
  svgOnHover?: React.ReactNode;
  rounded?: boolean;
  type?: "button" | "submit" | "reset";
};

export const SvgButton = ({
  reference,
  svg = null,
  text = "",
  onClick = () => {},
  extraClass = "",
  size = "small",
  confirmations = [],
  title = "",
  tabIndex = 0,
  transparent = true,
  svgOnHover = null,
  rounded = true,
  type = "button",
}: SvgButtonProps) => {
  const [innerText, setInnerText] = useState(text);
  const [currentSvg, setCurrentSvg] = useState(svg);
  const [pendingConfirmations, setPendingConfirmations] =
    useState(confirmations);

  const handleClick = () => {
    if (pendingConfirmations.length === 0) {
      onClick();
      setPendingConfirmations(confirmations);
    } else {
      setInnerText(pendingConfirmations[0]);
      setPendingConfirmations(pendingConfirmations.slice(1));
    }
  };

  useEffect(() => {
    setInnerText(text);
  }, [text]);

  return (
    <button
      type={type}
      tabIndex={tabIndex}
      className={`svg-button ${rounded ? "rounded" : ""} clickeable ${extraClass} ${size} ${transparent ? "transparent" : ""}`}
      onClick={handleClick}
      onMouseEnter={() => {
        if (svgOnHover) {
          setCurrentSvg(svgOnHover);
        }
      }}
      onMouseLeave={() => {
        setCurrentSvg(svg);
      }}
      title={title}
      ref={reference}
    >
      {svg && (
        <div className="d-flex align-center justify-center">{currentSvg}</div>
      )}
      {innerText && <p>{innerText}</p>}
    </button>
  );
};
