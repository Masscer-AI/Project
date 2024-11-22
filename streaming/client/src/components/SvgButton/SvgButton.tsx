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
}: SvgButtonProps) => {
  const [innerText, setInnerText] = useState(text);
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
      tabIndex={tabIndex}
      className={`svg-button d-flex align-center justify-center clickeable ${extraClass} ${size}`}
      onClick={handleClick}
      title={title}
      ref={reference}
    >
      {svg && <div className="d-flex align-center justify-center">{svg}</div>}
      {innerText && (
        <div className="d-flex align-center justify-center fit-content">
          {innerText}
        </div>
      )}
    </button>
  );
};
