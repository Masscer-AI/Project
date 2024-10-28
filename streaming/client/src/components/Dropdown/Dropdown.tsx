import React, { useState } from "react";
import "./Dropdown.css";

type TFloatingDropdownProps = {
  children: React.ReactNode;
  opener: React.ReactNode;
  left?: string;
  top?: string;
  right?: string;
};

export const FloatingDropdown = ({
  children,
  opener,
  left = undefined,
  top = "0",
  right = undefined,
}: TFloatingDropdownProps) => {
  const [isOpened, setIsOpened] = useState(false);

  return (
    <div className={`floating-dropdown `}>
      <div onClick={() => setIsOpened(!isOpened)}>{opener}</div>
      {
        <div
          style={{
            display: isOpened ? "flex" : "none",
            top: top,
            left: left,
            right: right,
          }}
          className="__content"
        >
          {children}
        </div>
      }
    </div>
  );
};
