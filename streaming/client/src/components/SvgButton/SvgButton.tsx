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
}: SvgButtonProps) => {
  const [innerText, setInnerText] = useState(text);
  const [pendingConfirmations, setPendingConfirmations] =
    useState(confirmations);

  const handleClick = () => {
    if (pendingConfirmations.length === 0) {
      onClick();
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
      tabIndex={0}
      className={`svg-button clickeable ${extraClass} ${size}`}
      onClick={handleClick}
      title={title}
      ref={reference}
    >
      <span>{svg}</span>
      <span>{innerText}</span>
    </button>
  );
};
