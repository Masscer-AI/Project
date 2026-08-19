import React, { useLayoutEffect, useRef, useState } from "react";
import { MantineProvider } from "@mantine/core";
import { Outlet } from "react-router-dom";

const WRAPPER_CLASS = "force-dark-public";

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
