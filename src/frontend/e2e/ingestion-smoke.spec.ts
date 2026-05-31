import { expect, test } from "@playwright/test";
import path from "node:path";

test.skip(
  process.env.RUN_FRONTEND_E2E !== "true",
  "Set RUN_FRONTEND_E2E=true with the API server running to execute this smoke test.",
);

test("uploads a small fixture and shows a tracked job", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Ingest Orquestator" })).toBeVisible();

  await page
    .locator('input[type="file"]')
    .setInputFiles(path.resolve(process.cwd(), "../../sample-inputs/sample.md"));
  await page.getByRole("button", { name: /Ingest 1 file/ }).click();

  await expect(page.getByText("sample.md")).toBeVisible();
  await expect(page.getByText(/parser queued|parsing|completed|failed/)).toBeVisible({
    timeout: 20_000,
  });
});
