import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";

export default defineConfig({
  plugins: [react()],
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
      input: "./client/src/widget/widgetEntry.tsx",
      output: {
        entryFileNames: "assets/chat-widget.js",
        format: "iife",
        name: "ChatWidget",
      },
    },
  },
});
