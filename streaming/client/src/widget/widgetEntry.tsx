import React from "react";
import { createRoot } from "react-dom/client";
import ChatWidget from "./ChatWidget";
import { WidgetConfig } from "./widgetStore";

// This will be called by the loader script
(window as any).initChatWidget = (
  config: WidgetConfig,
  sessionToken: string,
  widgetToken: string,
  streamingUrl: string
) => {
  // Check if widget is already initialized
  const existingRoot = document.getElementById("chat-widget-root");
  if (existingRoot) {
    console.log("Widget already initialized, skipping");
    return;
  }

  // Store streaming URL globally as fallback
  (window as any).WIDGET_STREAMING_URL = streamingUrl;
  console.log("Widget initialized with streaming URL:", streamingUrl);

  // Create a container for the widget
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

  // Store root for cleanup if needed
  (window as any).__chatWidgetRoot = root;
};

