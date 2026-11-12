import { expect, test } from "@playwright/test";
import { password, signIn } from "./signIn";

test("a page without a session goes to sign-in", async ({ page }) => {
  await page.goto("/scoreboard");

  await expect(
    page.getByRole("heading", { name: "Sign in to UnderCover" }),
  ).toBeVisible();
});

test("a wrong password shows the reason and stays on sign-in", async ({
  page,
}) => {
  await page.goto("/");
  await page
    .getByLabel("Email address")
    .fill("dana.whitfield@undercover.example");
  await page.getByLabel("Password").fill(`${password}-wrong`);
  await page.getByRole("button", { name: "Sign in" }).click();

  await expect(page.getByRole("alert")).toHaveText("Invalid login credentials");
});

test("a handler signs in, the header names them, and signing out returns to sign-in", async ({
  page,
}) => {
  await signIn(page, "marcus.oyelaran");
  await expect(page.getByText("Marcus Oyelaran")).toBeVisible();

  await page.getByRole("button", { name: "Sign out" }).click();

  await expect(
    page.getByRole("heading", { name: "Sign in to UnderCover" }),
  ).toBeVisible();
});

test("a handler who can't sign off is told why on a held payout", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1008";
  await request.post(`/api/claims/${claimId}/decision`, {
    data: {
      decision: "approve",
      payout: "1300.00",
      reason: "A payout over the approval limit.",
      policy_reference: "Section 7",
    },
  });
  await signIn(page, "marcus.oyelaran");

  await page.goto(`/claims/${claimId}`);

  await expect(page.getByText(/Marcus Oyelaran can't sign off/)).toBeVisible();
  await expect(page.getByRole("button", { name: /Sign off/ })).toHaveCount(0);
});
