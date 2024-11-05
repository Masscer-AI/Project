import React, { useState } from "react";
import "./Dropdown.css";

type TFloatingDropdownProps = {
  children: React.ReactNode;
  opener: React.ReactNode;
  left?: string;
  top?: string;
  right?: string;
  bottom?: string;
  transform?: string;
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
  transform = undefined,
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
              bottom: bottom,
              transform: transform,
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
