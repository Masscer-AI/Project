import React from "react";
import { useStore } from "../../modules/store";
export const Themer = () => {
  const { userPreferences } = useStore((s) => ({
    userPreferences: s.userPreferences,
  }));
  return <div id="themer" className={`${userPreferences.theme}`} />;
};
