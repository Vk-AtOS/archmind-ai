import { defineConfig } from "@playwright/test";

// Runs against a running stack (make up). E2E_EMAIL / E2E_PASSWORD come from `make e2e`.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  retries: 0,
  use: { baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000", trace: "retain-on-failure" },
});
