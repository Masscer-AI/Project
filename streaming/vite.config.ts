import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import { preserveWidgetPlugin } from "./vite-preserve-widget-plugin";

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  // Check for widget build via command line args or env var
  const isWidgetBuild = process.argv.includes('--widget') || process.env.BUILD_WIDGET === "true";

  if (isWidgetBuild) {
    // Widget build configuration
    return {
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
        emptyOutDir: false, // Don't delete existing files when building widget
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

  // Main app build configuration
  return {
    plugins: [react(), preserveWidgetPlugin()],
    root: "./client",
    envDir: "../../",
    define: {
      //polifil to avoid process from being undefined
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
          // chunkFileNames: 'bundle.js',
          // assetFileNames: 'bundle.[ext]'
        },
      },
    },
    server: {},
  };
});
