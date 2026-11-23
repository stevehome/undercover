import { expect } from "@playwright/test";
import { test } from "./signIn";
import type { APIRequestContext } from "@playwright/test";
import { agentHeaders } from "./agentKey";
import { askedFor, currentRun, startDispatch } from "./startedWork";

/** The dispatch the app created, once the agent was asked to work it. */
async function dispatchStarted(request: APIRequestContext) {
  const run = await currentRun(request);
  const asked = await askedFor(request, "work_run");
  const taken = asked.some((body) => body.run_id === run?.run_id);
  return run?.kind === "dispatch" && taken ? run.concurrency : null;
}

test("starting a dispatch creates it for 3 claim agents and asks the agent to work it", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Claim agents at once")).toHaveValue("3");

  await page.getByRole("button", { name: "Start a dispatch" }).click();

  await expect.poll(() => dispatchStarted(request)).toBe(3);
});

test("starting a dispatch with a changed number creates it for that many", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByLabel("Claim agents at once").fill("7");

  await page.getByRole("button", { name: "Start a dispatch" }).click();

  await expect.poll(() => dispatchStarted(request)).toBe(7);
});

test("the queue page shows a dispatch's claims, cost, time and summary", async ({
  page,
  request,
}) => {
  const run = await startDispatch(request, 3);
  const [first, second] = run.claims.map((claim) => claim.claim_id);
  await request.post(`/api/runs/${String(run.run_id)}/claims/${first}`, {
    headers: agentHeaders,
    data: { status: "done", note: "Declined" },
  });
  await request.post(`/api/runs/${String(run.run_id)}/claims/${second}`, {
    headers: agentHeaders,
    data: { status: "still in progress", note: "Left in progress" },
  });
  await request.post(`/api/claims/${first}/model-calls`, {
    headers: agentHeaders,
    data: {
      run_id: run.run_id,
      model: "stub/model",
      input_tokens: 10,
      output_tokens: 5,
      total_tokens: 15,
      cost: "0.003120000",
    },
  });
  await request.post(`/api/claims/${first}/work-segments`, {
    headers: agentHeaders,
    data: {
      run_id: run.run_id,
      started_on: "2026-01-01T00:00:00+00:00",
      finished_on: "2026-01-01T00:00:12+00:00",
    },
  });
  await request.post(`/api/runs/${String(run.run_id)}/finish`, {
    headers: agentHeaders,
  });

  await page.goto("/");

  await expect(page.getByText("The current dispatch (finished)")).toBeVisible();
  await expect(
    page.getByText("Model cost $0.0031, working time 12.0 s"),
  ).toBeVisible();
  await expect(page.getByText("Still in progress: " + second)).toBeVisible();
  await expect(
    page
      .getByRole("region", { name: "The current run" })
      .getByRole("link", { name: second }),
  ).toBeVisible();
});
