import { expect } from "@playwright/test";
import { handlerHeaders, test } from "./signIn";
import { agentHeaders } from "./agentKey";
import { recordDecision } from "./decisions";

test("the queue page lists the claims", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "The claims queue" }),
  ).toBeVisible();
  await expect(
    page.getByRole("table").getByRole("link", { name: "CLM-1001" }),
  ).toBeVisible();
});

test("the queue shows a claim's status as it moves through its states", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1005";
  const row = () => page.getByRole("row", { name: new RegExp(claimId) });

  await page.goto("/");
  await expect(row()).toContainText("waiting");

  await request.post(`/api/claims/${claimId}/steps`, {
    headers: agentHeaders,
    data: {
      kind: "note",
      text: "Read the claim, its policy and the customer's claim history",
      details: {},
    },
  });
  await page.goto("/");
  await expect(row()).toContainText("in progress");

  await recordDecision(request, claimId, {
    decision: "approve",
    payout: "1250.00",
    reason: "A passport lost while swimming, replaced abroad.",
    policy_reference: "Section 6",
  });
  await page.goto("/");
  await expect(row()).toContainText("waiting for sign-off");

  await request.post(`/api/claims/${claimId}/sign-off`, {
    headers: await handlerHeaders(request),
  });
  await page.goto("/");
  await expect(row()).toContainText("decided");
});
