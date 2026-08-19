import React from "react";
import { createRoot } from "react-dom/client";
import ChatWidget from "./ChatWidget";
import { WidgetConfig } from "./widgetStore";

(window as any).initChatWidget = (
  config: WidgetConfig,
  sessionToken: string,
  widgetToken: string,
  streamingUrl: string
) => {
  const existingRoot = document.getElementById("chat-widget-root");
  if (existingRoot) {
    console.log("Widget already initialized, skipping");
    return;
  }

  (window as any).WIDGET_STREAMING_URL = streamingUrl;
  console.log("Widget initialized with streaming URL:", streamingUrl);

  const container = document.createElement("div");
  container.id = "chat-widget-root";
  document.body.appendChild(container);

  const root = createRoot(container);
  root.render(
    <ChatWidget
      config={config}
      sessionToken={sessionToken}
      widgetToken={widgetToken}
      streamingUrl={streamingUrl}
    />
  );

  (window as any).__chatWidgetRoot = root;
};
