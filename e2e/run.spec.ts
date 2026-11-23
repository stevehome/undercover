import { expect } from "@playwright/test";
import { test } from "./signIn";
import { agentHeaders } from "./agentKey";
import { askedFor, currentRun, startEvaluation } from "./startedWork";
import { recordDecision } from "./decisions";

test("the scoreboard shows an evaluation played out through the API", async ({
  page,
  request,
}) => {
  const run = await startEvaluation(request, "held_out", true);
  expect(run.claims).toHaveLength(5);
  for (const claim of run.claims) {
    await recordDecision(request, claim.claim_id, {
      decision: "decline",
      payout: "0.00",
      reason: "Not covered.",
      policy_reference: "Section 1",
    });
  }
  await request.post(`/api/runs/${String(run.run_id)}/finish`, {
    headers: agentHeaders,
  });

  await page.goto("/scoreboard");

  const row = page.getByRole("row", { name: /The held-out set, tiny/ });
  await expect(row).toContainText("finished");
  await expect(row).toContainText("%");
  await expect(row).toContainText("2.10");
  for (const heading of [
    "Decision accuracy",
    "Accuracy",
    "Grade",
    "Cost of mistakes",
    "Straight through",
    "Model cost per claim",
    "Time per claim",
    "Run time",
  ]) {
    await expect(
      page.getByRole("columnheader", { name: heading, exact: true }),
    ).toBeVisible();
  }

  await row.getByRole("link").click();
  await expect(page.getByRole("heading", { name: /Evaluation/ })).toBeVisible();
  await expect(page.getByRole("row", { name: /decline/ })).toHaveCount(5);
  await expect(
    page.getByRole("row", { name: /decline/ }).first(),
  ).toContainText("B (2.10)YesYes");
  const copy = run.claims[0].claim_id;
  await page.goto(`/claims/${copy}`);
  await expect(page.getByRole("button", { name: /Sign off/ })).toHaveCount(0);
});

test("the queue is as it was after an evaluation", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByRole("link", { name: "CLM-1001" })).toBeVisible();
  const before = await page.getByRole("row").count();

  const run = await startEvaluation(request, "evaluation", false);
  await request.post(`/api/runs/${String(run.run_id)}/finish`, {
    headers: agentHeaders,
  });
  await page.goto("/");

  await expect(page.getByRole("row")).toHaveCount(before);
});

test("starting an evaluation on the scoreboard creates it with N and the set and asks the agent to work it", async ({
  page,
  request,
}) => {
  await page.goto("/scoreboard");
  await page.getByLabel("Claim agents at once").fill("9");
  await page.getByLabel("Set").selectOption("held_out");
  await page.getByLabel("Only the 5 tiny claims").check();

  await page.getByRole("button", { name: "Start an evaluation" }).click();

  await expect
    .poll(async () => {
      const run = await currentRun(request);
      const asked = await askedFor(request, "work_run");
      return asked.some((body) => body.run_id === run?.run_id) ? run : null;
    })
    .toMatchObject({
      kind: "evaluation",
      concurrency: 9,
      eval_set: "held_out",
      tiny: true,
    });
});
