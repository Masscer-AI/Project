import React, { useEffect, useState } from "react";
import { useStore } from "../../modules/store";

export const Themer = () => {
  const { userPreferences } = useStore((s) => ({
    userPreferences: s.userPreferences,
  }));

  const [systemDark, setSystemDark] = useState(
    window.matchMedia("(prefers-color-scheme: dark)").matches
  );

  useEffect(() => {
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = (e: MediaQueryListEvent) => setSystemDark(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  const resolved =
    userPreferences.theme === "system"
      ? systemDark
        ? "dark"
        : "light"
      : userPreferences.theme || "dark";

  return <div id="themer" className={resolved} />;
};
