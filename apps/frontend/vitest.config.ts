import path from "node:path";

import { defineConfig } from "vitest/config";

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  // ``tsconfig.json`` ships with ``"jsx": "preserve"`` so Next.js can do the
  // transform itself in production builds. Vitest 4 / vite 8 delegates JSX
  // loading to oxc — without an explicit transform mode every ``.tsx`` test
  // file fails to parse with "Unexpected JSX expression". Setting the oxc
  // jsx runtime to 'automatic' here affects test loads only; the Next build
  // is unaffected.
  oxc: {
    jsx: { runtime: "automatic" },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
});
