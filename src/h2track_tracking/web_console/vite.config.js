import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { resolve } from "node:path";

export default defineConfig({
  plugins: [react()],
  base: "/",
  build: {
    outDir: resolve(__dirname, "../h2track_tracking/static_console"),
    emptyOutDir: true
  }
});
