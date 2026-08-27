import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  test: {
    globals: true,
    // Node by default: the helper tests in api.test.ts need no DOM and are
    // faster without one. Files that render components ask for jsdom with a
    // `// @vitest-environment jsdom` docblock — see App.test.tsx.
    environment: "node",
  },
});
