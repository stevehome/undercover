import { mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { defineConfig } from "@playwright/test";

/** A fresh database for each run, so the backend never holds a deleted file. */
const databasePath = path.join(
  mkdtempSync(path.join(tmpdir(), "undercover-e2e-")),
  "test.db",
);

const authStandIn = "http://127.0.0.1:8004";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  // Only one dispatch or evaluation can run at a time, so the specs take turns.
  workers: 1,
  use: { baseURL: "http://localhost:5183" },
  webServer: [
    {
      command: "node e2e/authStandIn.mjs",
      url: `${authStandIn}/auth/v1/.well-known/jwks.json`,
    },
    {
      command: "node e2e/judgeStandIn.mjs",
      url: "http://127.0.0.1:8005/calls",
    },
    {
      command: "node e2e/agentStandIn.mjs",
      url: "http://127.0.0.1:8003/calls",
    },
    {
      command: "uv run -m uvicorn backend.main:app --port 8010",
      url: "http://127.0.0.1:8010/api/health",
      env: {
        UNDERCOVER_AGENT: "http://127.0.0.1:8003",
        VITE_SUPABASE_URL: authStandIn,
        OPENROUTER_ORIGIN: "http://127.0.0.1:8005",
        OPENROUTER_API_KEY: "e2e-key",
        DATABASE_URL: "",
        DATABASE_PATH: databasePath,
      },
    },
    {
      command: "npx vite dashboard --port 5183 --strictPort",
      url: "http://localhost:5183",
      // Never a dev server that holds the real project's address.
      reuseExistingServer: false,
      env: {
        UNDERCOVER_BACKEND: "http://127.0.0.1:8010",
        VITE_SUPABASE_URL: authStandIn,
        VITE_SUPABASE_PUBLISHABLE_KEY: "e2e-key",
      },
    },
  ],
});
