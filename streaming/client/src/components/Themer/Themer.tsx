import React from "react";
import { useStore } from "../../modules/store";
export const Themer = () => {
  const { theme, setTheme } = useStore((s) => ({
    theme: s.theme,
    setTheme: s.setTheme,
  }));
  return <div id="themer" className={`${theme}`} />;
};
