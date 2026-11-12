import { expect } from "@playwright/test";
import { test } from "./signIn";
import type { APIRequestContext } from "@playwright/test";

const standIn = "http://127.0.0.1:8003";

async function evaluationsAsked(request: APIRequestContext) {
  const paths = (await (
    await request.get(`${standIn}/calls`)
  ).json()) as string[];
  const bodies = (await (await request.get(`${standIn}/bodies`)).json()) as {
    concurrency: number;
    eval_set: string;
    tiny: boolean;
  }[];
  return bodies.filter((_, index) => paths[index] === "/api/evaluations");
}

test("the scoreboard shows an evaluation played out through the API", async ({
  page,
  request,
}) => {
  const run = (await (
    await request.post("/api/runs/evaluation", {
      data: {
        concurrency: 5,
        eval_set: "held_out",
        tiny: true,
        model: "stub/model",
        reasoning_effort: "low",
        configuration_version: 1,
      },
    })
  ).json()) as { run_id: number; claims: { claim_id: string }[] };
  expect(run.claims).toHaveLength(5);
  for (const claim of run.claims) {
    await request.post(`/api/claims/${claim.claim_id}/decision`, {
      data: {
        decision: "decline",
        payout: "0.00",
        reason: "Not covered.",
        policy_reference: "Section 1",
      },
    });
  }
  await request.post(`/api/runs/${String(run.run_id)}/finish`);

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

  const run = (await (
    await request.post("/api/runs/evaluation", {
      data: {
        concurrency: 5,
        eval_set: "evaluation",
        tiny: false,
        model: "stub/model",
        reasoning_effort: "low",
        configuration_version: 1,
      },
    })
  ).json()) as { run_id: number };
  await request.post(`/api/runs/${String(run.run_id)}/finish`);
  await page.goto("/");

  await expect(page.getByRole("row")).toHaveCount(before);
});

test("starting an evaluation on the scoreboard reaches the agent's service with N and the set", async ({
  page,
  request,
}) => {
  await page.goto("/scoreboard");
  await page.getByLabel("Claim agents at once").fill("9");
  await page.getByLabel("Set").selectOption("held_out");
  await page.getByLabel("Only the 5 tiny claims").check();

  await page.getByRole("button", { name: "Start an evaluation" }).click();

  await expect
    .poll(() => evaluationsAsked(request))
    .toContainEqual({ concurrency: 9, eval_set: "held_out", tiny: true });
});
