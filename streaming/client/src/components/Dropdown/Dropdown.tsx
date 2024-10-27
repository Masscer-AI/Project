import React, { useState } from "react";
import "./Dropdown.css"
export const FloatingDropdown = ({ children, title }) => {
  const [isOpened, setIsOpened] = useState(false);

  return (
    <div className="floating-dropdown">
      <button className="button" onClick={() => setIsOpened(!isOpened)}>{title}</button>
      {isOpened && <div className="__content">{children}</div>}
    </div>
  );
};
