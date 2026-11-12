import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

/**
 * `npm run dev` reads the root `.env`. Under test the values are set here, or by
 * Playwright, and win over any file.
 */
export default defineConfig(({ mode }) => ({
  envDir: mode === "test" ? "." : "..",
  plugins: [react()],
  // Found at once, so a first page load never reloads for a new dependency.
  optimizeDeps: { include: ["@supabase/supabase-js"] },
  server: {
    proxy: {
      "/api": process.env.UNDERCOVER_BACKEND ?? "http://127.0.0.1:8000",
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    env: {
      VITE_SUPABASE_URL: "http://127.0.0.1:8004",
      VITE_SUPABASE_PUBLISHABLE_KEY: "test-key",
    },
    coverage: {
      include: ["src/**"],
      thresholds: { statements: 80 },
    },
  },
}));
