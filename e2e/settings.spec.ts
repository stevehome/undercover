import { expect, test as unsigned } from "@playwright/test";
import { signIn, test } from "./signIn";

test("a senior handler changes a setting, and the change is recorded", async ({
  page,
}) => {
  await page.goto("/settings");
  const limit = page.getByLabel("Improvement: Spending limit for each round");
  await expect(limit).toHaveValue("0.50");

  await limit.fill("0.75");
  await page
    .getByRole("row", { name: /Spending limit/ })
    .getByRole("button", { name: "Save" })
    .click();
  await expect(page.getByRole("dialog")).toContainText("from 0.50 to 0.75");
  await page.getByRole("button", { name: "Change it" }).click();

  await expect(page.getByRole("row", { name: /Spending limit/ })).toContainText(
    "Dana Whitfield",
  );
  await expect(limit).toHaveValue("0.75");
});

test("the appearance switches both ways and the browser remembers it", async ({
  page,
}) => {
  await page.goto("/settings");
  const root = page.locator("html");

  await page.getByLabel("Dark").check();
  await expect(root).toHaveAttribute("data-theme", "dark");
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(4, 35, 46)",
  );

  await page.reload();
  await expect(root).toHaveAttribute("data-theme", "dark");

  await page.getByLabel("Light").check();
  await expect(root).toHaveAttribute("data-theme", "light");
  await expect(page.locator("body")).toHaveCSS(
    "background-color",
    "rgb(240, 244, 245)",
  );
});

unsigned(
  "a handler who can't change settings sees why and has nothing to edit",
  async ({ page }) => {
    await signIn(page, "marcus.oyelaran");
    await page.goto("/settings");

    await expect(
      page.getByText(/Marcus Oyelaran can't change settings/),
    ).toBeVisible();
    await expect(page.getByRole("textbox")).toHaveCount(0);
    await expect(
      page.getByRole("heading", { name: "Models allowed" }),
    ).toBeVisible();
    await expect(page.getByText("openai/gpt-6-luna")).toBeVisible();
  },
);
