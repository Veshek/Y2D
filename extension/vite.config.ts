import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Two build passes are needed because IIFE format (required for content scripts
// and MV3 service workers) does not support multiple inputs.
//
// Pass 1 (default): popup HTML — React app, ES module output.
// Pass 2 (VITE_BUILD_SCRIPTS=1): content.ts + background.ts — IIFE output.
//
// The package.json "build" script runs both passes sequentially.

// VITE_BUILD_ENTRY=content|background → single IIFE script pass (no emptyOutDir)
// default → popup HTML pass (clears dist first)
const scriptEntry = process.env.VITE_BUILD_ENTRY as "content" | "background" | undefined;

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "dist",
    emptyOutDir: !scriptEntry,
    rollupOptions: scriptEntry
      ? {
          input: { [scriptEntry]: `src/${scriptEntry}.ts` },
          output: {
            entryFileNames: "[name].js",
            format: "iife",
          },
        }
      : {
          input: "index.html",
          output: {
            entryFileNames: "assets/[name]-[hash].js",
            format: "es",
          },
        },
  },
});
