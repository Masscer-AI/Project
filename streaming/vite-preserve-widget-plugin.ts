import type { Plugin } from 'vite';
import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'fs';
import { dirname, join } from 'path';

/**
 * Plugin to preserve chat-widget.js during main app build
 */
export function preserveWidgetPlugin(): Plugin {
  let widgetPath: string | null = null;
  let widgetContent: Buffer | null = null;

  return {
    name: 'preserve-widget',
    configResolved() {
      // Save widget file before Vite cleans the directory
      const distAssetsPath = join(process.cwd(), 'client', 'dist', 'assets', 'chat-widget.js');
      if (existsSync(distAssetsPath)) {
        widgetPath = distAssetsPath;
        widgetContent = readFileSync(distAssetsPath);
        console.log('Preserving chat-widget.js...');
      }
    },
    writeBundle() {
      // Restore widget file after bundles are written
      if (widgetPath && widgetContent) {
        const distAssetsDir = dirname(widgetPath);
        // Ensure assets directory exists
        if (!existsSync(distAssetsDir)) {
          mkdirSync(distAssetsDir, { recursive: true });
        }
        writeFileSync(widgetPath, widgetContent);
        console.log('Restored chat-widget.js');
      }
    },
  };
}

