import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import { preserveWidgetPlugin } from "./vite-preserve-widget-plugin";
import tailwindcss from '@tailwindcss/vite'
export default defineConfig(({ command, mode }) => {
  const isWidgetBuild = process.argv.includes('--widget') || process.env.BUILD_WIDGET === "true";

  if (isWidgetBuild) {
    return {
      plugins: [react(), tailwindcss()],
      root: "./client",
      envDir: "../../",
      define: {
        "process.env": {
          environment: "DEV",
        },
      },
      build: {
        minify: true,
        chunkSizeWarningLimit: 2000000,
        assetsDir: "assets",
        outDir: "dist",
        emptyOutDir: false,
        rollupOptions: {
          input: "./src/widget/widgetEntry.tsx",
          output: {
            entryFileNames: "assets/chat-widget.js",
            format: "iife",
            name: "ChatWidget",
          },
        },
      },
    };
  }

  return {
    plugins: [react(), tailwindcss(), preserveWidgetPlugin()],
    root: "./client",
    envDir: "../../",
    define: {
      "process.env": {
        environment: "DEV",
      },
    },
    build: {
      minify: true,
      chunkSizeWarningLimit: 2000000,
      assetsDir: "assets",
      rollupOptions: {
        output: {
          entryFileNames: "assets/[hash].bundle.js",
        },
      },
    },
    server: {},
  };
});
