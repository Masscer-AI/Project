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
  extraClass?: string;
};

export const FloatingDropdown = ({
  children,
  opener,
  isOpened,
  left = undefined,
  top = undefined,
  right = undefined,
  bottom = undefined,
  transform = undefined,
  extraClass = "",
}: TFloatingDropdownProps) => {
  return (
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
          className={`__content ${extraClass}`}
        >
          {children}
        </div>
      }
    </div>
  );
};
