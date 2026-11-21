import type { APIRequestContext } from "@playwright/test";
import { expect } from "@playwright/test";
import { test } from "./signIn";
import { agentHeaders } from "./agentKey";
import { recordDecision } from "./decisions";

const source = {
  system: "Policy administration",
  owner: "Product",
  reviewed: "2026-09-01",
};

async function step(
  request: APIRequestContext,
  claimId: string,
  kind: string,
  text: string,
  details: object,
) {
  await request.post(`/api/claims/${claimId}/steps`, {
    headers: agentHeaders,
    data: { kind, text, details },
  });
}

test("a claim's page shows every step, where the agent's context came from and the whole decision", async ({
  page,
  request,
}) => {
  const claimId = "CLM-1011";
  await step(
    request,
    claimId,
    "tool_call",
    "Called undercover-context___get_plan",
    {
      tool: "undercover-context___get_plan",
    },
  );
  await step(request, claimId, "lookup", "Looked up the premium plan", {
    files: { "plans.yaml": source },
  });
  await step(
    request,
    claimId,
    "refusal",
    "Refused by the Gateway: Tool Execution Denied",
    { source: "the Gateway", detail: "Tool Execution Denied" },
  );
  await recordDecision(request, claimId, {
    decision: "approve",
    payout: "300.00",
    reason: "A lost suitcase, covered up to the plan's limit.",
    policy_reference: "Section 5",
  });

  await page.goto(`/claims/${claimId}`);

  await expect(
    page.getByText("Called undercover-context___get_plan"),
  ).toBeVisible();
  await expect(page.getByText("Refused by the Gateway")).toBeVisible();
  await expect(page.locator("li.refusal")).toHaveCount(1);

  await expect(
    page.getByRole("heading", { name: "Context used" }),
  ).toBeVisible();
  await expect(page.getByRole("heading", { name: "plans.yaml" })).toBeVisible();
  await expect(
    page.getByText("Policy administration, owned by Product"),
  ).toBeVisible();

  await expect(page.getByText("approve, $300.00")).toBeVisible();
  await expect(page.getByText("The end-to-end test")).toBeVisible();
  await expect(page.getByText(/^Version 2026\./)).toBeVisible();
  await expect(page.getByText("How the payout was worked out")).toBeVisible();
  await expect(page.getByRole("cell", { name: "Expense" })).toBeVisible();
});
