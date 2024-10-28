import React from "react";

export const Checkbox = ({ checked, onChange }) => {
  return <input type="checkbox" checked={checked} onChange={onChange} />;
};
