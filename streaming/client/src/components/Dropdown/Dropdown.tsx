import React, { useState, useEffect, useRef } from "react";
import "./Dropdown.css";
import toast from "react-hot-toast";
import { debounce } from "../../modules/utils";

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
  const dropdownRef = useRef<HTMLDivElement | null>(null);
  const [dropdownStyle, setDropdownStyle] = useState<{
    [key: string]: string | undefined;
  }>({
    top,
    left,
    right,
    bottom,
    transform,
  });
  const [adjusted, setAdjusted] = useState(false);
  const [innerIsOpened, setInnerIsOpened] = useState(isOpened);
  const [timeoutId, setTimeoutId] = useState<number | null>(null);

  const adjustDropdown = () => {
    if (dropdownRef.current) {
      const { innerWidth, innerHeight } = window;
      const dropdownRect = dropdownRef.current.getBoundingClientRect();

      const newStyles = {
        top,
        left,
        right,
        bottom,
        transform,
      };


      if (dropdownRect.left < 0) {
        if (left) {
          newStyles.left = `calc(${left} + ${Math.abs(dropdownRect.left)}px)`;
        }
      }
      if (dropdownRect.right > innerWidth) {
        let newLeft = `calc( ${left} - ${dropdownRect.right - innerWidth}px) `;
        newStyles.left = newLeft;
      }
      if (dropdownRect.bottom > innerHeight) {
        if (bottom) {
          newStyles.bottom = `calc(${bottom} - ${dropdownRect.bottom - innerHeight}px)`;
        } else {
          newStyles.top = `calc(${top} - ${dropdownRect.bottom - innerHeight}px)`;
        }
      }
      if (dropdownRect.top < 0) {
        if (top) {
          newStyles.top = `calc(${top} + ${Math.abs(dropdownRect.top)}px)`;
        } else {
          newStyles.bottom = `calc(${bottom} - ${Math.abs(dropdownRect.top)}px)`;
        }
      }
      setDropdownStyle(newStyles);
      setAdjusted(true);
    }
  };

  const onMouseLeave = () => {
    const id = setTimeout(() => {
      setInnerIsOpened(false);
      setTimeoutId(null);
    }, 200);
    setTimeoutId(id);
  };

  const onMouseEnter = () => {
    if (timeoutId) {
      clearTimeout(timeoutId);
      setTimeoutId(null);
    }
    setInnerIsOpened(true);
  };

  useEffect(() => {
    adjustDropdown();
  }, [innerIsOpened]);

  return (
    <div
      className={`floating-dropdown`}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {opener}
      {
        <div
          ref={dropdownRef}
          style={{
            display: innerIsOpened ? "flex" : "none",
            ...dropdownStyle,
          }}
          className={`__content ${extraClass}`}
        >
          {children}
        </div>
      }
    </div>
  );
};
