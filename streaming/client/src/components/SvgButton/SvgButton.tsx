import React, { useState, useEffect, LegacyRef } from "react";

type SvgButtonProps = {
  svg?: React.ReactNode;
  text?: string;
  onClick?: () => void;
  extraClass?: string;
  disabled?: boolean;
  size?: "small" | "big";
  confirmations?: string[];
  title?: string;
  reference?: LegacyRef<HTMLButtonElement>;
  tabIndex?: number;
  transparent?: boolean;
  svgOnHover?: React.ReactNode;
  rounded?: boolean;
  type?: "button" | "submit" | "reset";
  isActive?: boolean;
};

export const SvgButton = ({
  reference,
  svg = null,
  text = "",
  onClick = () => { },
  extraClass = "",
  size = "small",
  disabled = false,
  confirmations = [],
  title = "",
  tabIndex = 0,
  transparent = true,
  svgOnHover = null,
  rounded = true,
  type = "button",
  isActive = false,
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

  const baseClasses =
    "group inline-flex items-center justify-center flex-row gap-2 cursor-pointer transition-all duration-200 focus:outline-none focus-visible:ring-2 focus-visible:ring-white/30 disabled:opacity-50 disabled:cursor-not-allowed";
  const shapeClass = rounded ? "rounded-md" : "rounded-sm";
  const paddingClass = innerText ? "px-4 py-2 text-sm" : "p-2";
  const variantClass = transparent
    ? "bg-transparent border border-transparent hover:bg-white/15 active:bg-white/20"
    : "bg-[rgba(35,33,39,0.5)] text-white border border-[rgba(156,156,156,0.3)] hover:bg-white hover:text-gray-900 active:bg-gray-100 svg-btn-hover-invert";
  const activeClass = isActive
    ? "!bg-white !text-gray-900 !border-white/30 svg-btn-active"
    : "";

  return (
    <button
      type={type}
      tabIndex={tabIndex}
      aria-pressed={isActive || undefined}
      className={`${baseClasses} ${shapeClass} ${paddingClass} ${variantClass} ${activeClass} ${extraClass} ${size} `}
      onClick={handleClick}
      disabled={disabled}
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
      {innerText && <span className="svg-btn-text">{innerText}</span>}
    </button>
  );
};
