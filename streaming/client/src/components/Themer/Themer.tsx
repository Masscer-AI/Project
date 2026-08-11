import React, { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { useStore } from "../../modules/store";
import { isForceDarkPublicPath } from "../../utils/forceDarkPublicPath";

export const Themer = () => {
  const { pathname } = useLocation();
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

  const resolved = isForceDarkPublicPath(pathname)
    ? "dark"
    : userPreferences.theme === "system"
      ? systemDark
        ? "dark"
        : "light"
      : userPreferences.theme || "dark";

  return <div id="themer" className={resolved} />;
};
