import React, { useEffect, useRef, useState } from "react";

const MIFIEL_SCRIPT_SRC = "https://app.mifiel.com/widget-component/index.js";
const MIFIEL_SCRIPT_ID = "mifiel-widget-script";

function ensureMifielScriptLoaded(): Promise<void> {
  return new Promise((resolve, reject) => {
    const existing = document.getElementById(
      MIFIEL_SCRIPT_ID
    ) as (HTMLScriptElement & { _loaded?: boolean }) | null;
    if (existing) {
      if (existing._loaded) {
        resolve();
      } else {
        existing.addEventListener("load", () => resolve());
      }
      return;
    }
    const script = document.createElement("script") as HTMLScriptElement & {
      _loaded?: boolean;
    };
    script.type = "module";
    script.src = MIFIEL_SCRIPT_SRC;
    script.id = MIFIEL_SCRIPT_ID;
    script.addEventListener("load", () => {
      script._loaded = true;
      resolve();
    });
    script.addEventListener("error", () =>
      reject(new Error("Failed to load Mifiel widget script"))
    );
    document.head.appendChild(script);
  });
}

type MifielWidgetProps = {
  widgetId: string;
  environment: "production" | "sandbox";
  onSignSuccess: () => void;
  onSignError: (detail: unknown) => void;
};

export function MifielWidget({
  widgetId,
  environment,
  onSignSuccess,
  onSignError,
}: MifielWidgetProps) {
  const ref = useRef<HTMLElement | null>(null);
  const [scriptReady, setScriptReady] = useState(false);

  useEffect(() => {
    let cancelled = false;
    ensureMifielScriptLoaded()
      .then(() => {
        if (!cancelled) setScriptReady(true);
      })
      .catch((e) => {
        console.error(e);
        if (!cancelled) onSignError(e);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const el = ref.current;
    if (!el || !scriptReady) return;

    const handleSuccess = () => onSignSuccess();
    const handleError = (e: Event) => onSignError((e as CustomEvent).detail);

    el.addEventListener("signSuccess", handleSuccess);
    el.addEventListener("signError", handleError);
    return () => {
      el.removeEventListener("signSuccess", handleSuccess);
      el.removeEventListener("signError", handleError);
    };
  }, [scriptReady, onSignSuccess, onSignError]);

  if (!scriptReady) return null;

  return (
    <mifiel-widget
      ref={ref as React.Ref<HTMLElement>}
      id={widgetId}
      environment={environment}
      success-btn-text="Continuar"
      container-class="mifiel-widget-container"
    />
  );
}
