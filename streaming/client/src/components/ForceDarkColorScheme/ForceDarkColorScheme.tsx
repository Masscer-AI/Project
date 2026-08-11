import React, { useLayoutEffect, useRef, useState } from "react";
import { MantineProvider } from "@mantine/core";
import { Outlet } from "react-router-dom";

const WRAPPER_CLASS = "force-dark-public";

/**
 * Landing/auth UIs are hard-coded for dark panels. Scope a dark Mantine scheme
 * to this subtree so OS/user light theme does not produce dark-on-dark text,
 * without mutating the root `data-mantine-color-scheme` for the rest of the app.
 */
export function ForceDarkColorScheme() {
  const ref = useRef<HTMLDivElement>(null);
  const [root, setRoot] = useState<HTMLDivElement | null>(null);

  useLayoutEffect(() => {
    setRoot(ref.current);
  }, []);

  return (
    <div ref={ref} className={WRAPPER_CLASS} style={{ minHeight: "100%" }}>
      {root ? (
        <MantineProvider
          forceColorScheme="dark"
          cssVariablesSelector={`.${WRAPPER_CLASS}`}
          getRootElement={() => root}
        >
          <Outlet />
        </MantineProvider>
      ) : null}
    </div>
  );
}
