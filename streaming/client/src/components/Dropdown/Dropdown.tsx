import React, { useState } from "react";
import "./Dropdown.css";

type TFloatingDropdownProps = {
  children: React.ReactNode;
  opener: React.ReactNode;
  left?: string;
  top?: string;
  right?: string;
  bottom?: string;
  isOpened?: boolean;
};

export const FloatingDropdown = ({
  children,
  opener,
  isOpened,
  left = undefined,
  top = "0",
  right = undefined,
  bottom = undefined,
}: TFloatingDropdownProps) => {
  return (
    <>
      <div className={`floating-dropdown`}>
      {opener}
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
    </>
  );
};
