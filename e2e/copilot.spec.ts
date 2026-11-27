import { expect } from "@playwright/test";
import { handlerHeaders, signIn, test } from "./signIn";

const ASK = "Sign off on CLM-1003";

async function ask(page: import("@playwright/test").Page, text = ASK) {
  const box = page.getByLabel("Ask the Copilot");
  await box.fill(text);
  await box.press("Enter");
}

test("the Copilot's cards arrive one by one, the action stands out and a refusal shows its reason", async ({
  page,
}) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "Hello, Dana" }),
  ).toBeVisible();

  await ask(page);

  const sidebar = page.getByRole("complementary", { name: "Copilot" });
  await expect(sidebar.getByText("list_claims")).toBeVisible();
  await expect(sidebar.getByText("Working,")).toBeVisible();
  await expect(sidebar.getByText("Done, ")).toBeVisible();
  const action = sidebar.locator(".step-card.action", {
    hasText: "start_dispatch",
  });
  await expect(action).toBeVisible();
  await expect(action).toContainText("A dispatch is already running");
  await expect(sidebar.locator(".step-card:not(.action)")).toHaveCount(1);
});

test("the handler answers a confirmation with Sign off and pay and gets a formatted answer", async ({
  page,
}) => {
  await page.goto("/");
  await ask(page);

  const card = page.getByRole("region", { name: "Confirm the sign-off" });
  await expect(card).toContainText("CLM-1003");
  await expect(card).toContainText("Ana Souza");
  await expect(card).toContainText("$3,750.00");
  await expect(card).toContainText("Covered by section 3.");
  await expect(page.getByLabel("Ask the Copilot")).toBeDisabled();
  await expect(page.getByLabel("Ask the Copilot")).toHaveAttribute(
    "placeholder",
    "Answer the confirmation first",
  );

  await card.getByRole("button", { name: "Sign off and pay" }).click();

  const answer = page.locator(".message.from-copilot");
  await expect(answer.getByRole("table")).toBeVisible();
  await expect(answer.getByRole("listitem")).toContainText(
    "Nothing else needs you",
  );
  await expect(
    answer.getByRole("link", { name: "CLM-1003" }).first(),
  ).toHaveAttribute("href", "/claims/CLM-1003");
  await expect(answer).toContainText("3 model calls, $0.0012, 2.4 s");
  await expect(page.getByLabel("Ask the Copilot")).toBeEnabled();
});

test("Cancel pays nothing and the Copilot says so", async ({ page }) => {
  await page.goto("/");
  await ask(page);

  await page
    .getByRole("region", { name: "Confirm the sign-off" })
    .getByRole("button", { name: "Cancel" })
    .click();

  await expect(page.locator(".message.from-copilot")).toContainText(
    "I haven't signed off",
  );
  await expect(
    page.locator(".step-card", { hasText: "sign_off_claim" }),
  ).toContainText("The handler cancelled");
});

test("a reload keeps the waiting card and the conversation", async ({
  page,
}) => {
  await page.goto("/");
  await ask(page);
  await expect(
    page.getByRole("region", { name: "Confirm the sign-off" }),
  ).toBeVisible();

  await page.reload();

  await expect(
    page.getByRole("region", { name: "Confirm the sign-off" }),
  ).toBeVisible();
  await expect(page.getByText("list_claims")).toBeVisible();
});

test("a second handler doesn't see the first's conversation", async ({
  page,
  browser,
}) => {
  await page.goto("/");
  await ask(page);
  await expect(page.getByText("list_claims")).toBeVisible();

  const other = await browser.newPage();
  await signIn(other, "marcus.oyelaran");

  await expect(
    other.getByRole("heading", { name: "Hello, Marcus" }),
  ).toBeVisible();
  await expect(
    other.getByRole("navigation", { name: "Conversations" }),
  ).not.toContainText(ASK);
  await other.close();
});

test("the sidebar collapses to a tab, the page keeps working and it opens again", async ({
  page,
}) => {
  await page.goto("/");

  await page.getByRole("button", { name: "Collapse the Copilot" }).click();

  await expect(page.getByLabel("Ask the Copilot")).toBeHidden();
  await expect(page.getByRole("link", { name: "CLM-1001" })).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Ask the Copilot")).toBeHidden();
  await page.getByRole("button", { name: "Open the Copilot" }).click();
  await expect(page.getByLabel("Ask the Copilot")).toBeVisible();
});

test("on a narrow window the sidebar opens over the page", async ({ page }) => {
  await page.setViewportSize({ width: 700, height: 800 });
  await page.goto("/");

  const sidebar = page.getByRole("complementary", { name: "Copilot" });

  await expect(sidebar).toHaveCSS("position", "fixed");
});

test("the Copilot asks before paying redress, pays nothing on Cancel, and pays once on Pay redress", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await ask(page, "Pay the redress on CLM-1602");

  const card = page.getByRole("region", { name: "Confirm the redress" });
  await expect(card).toContainText("Gareth Ollander");
  for (const amount of ["$400.00", "$150.00", "$6.40", "$556.40"]) {
    await expect(card).toContainText(amount);
  }
  await expect(card).toContainText("The wording was unclear");
  const paid = async () =>
    (
      (await (
        await request.get("/api/claims/CLM-1602/appeal", {
          headers: await handlerHeaders(request),
        })
      ).json()) as { redress_payment: unknown }
    ).redress_payment;

  await card.getByRole("button", { name: "Cancel" }).click();
  await expect(page.getByText("I haven't paid it.")).toBeVisible();
  expect(await paid()).toBeNull();

  await ask(page, "Pay the redress on CLM-1602");
  await page
    .getByRole("region", { name: "Confirm the redress" })
    .getByRole("button", { name: "Pay redress" })
    .click();

  await expect(page.getByText(/I paid the redress on/)).toBeVisible();
  expect(await paid()).not.toBeNull();
});
