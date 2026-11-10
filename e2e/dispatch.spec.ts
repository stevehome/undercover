import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

const standIn = "http://127.0.0.1:8003";

async function dispatchesAsked(request: APIRequestContext) {
  const paths = (await (
    await request.get(`${standIn}/calls`)
  ).json()) as string[];
  const bodies = (await (await request.get(`${standIn}/bodies`)).json()) as {
    concurrency: number;
  }[];
  return bodies.filter((_, index) => paths[index] === "/api/dispatches");
}

test("starting a dispatch asks the agent's service for 3 claim agents", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await expect(page.getByLabel("Claim agents at once")).toHaveValue("3");

  await page.getByRole("button", { name: "Start a dispatch" }).click();

  await expect
    .poll(async () =>
      (await dispatchesAsked(request)).map((b) => b.concurrency),
    )
    .toContain(3);
});

test("starting a dispatch with a changed number asks for that many", async ({
  page,
  request,
}) => {
  await page.goto("/");
  await page.getByLabel("Claim agents at once").fill("7");

  await page.getByRole("button", { name: "Start a dispatch" }).click();

  await expect
    .poll(async () =>
      (await dispatchesAsked(request)).map((b) => b.concurrency),
    )
    .toContain(7);
});

test("the queue page shows a dispatch's claims, cost, time and summary", async ({
  page,
  request,
}) => {
  const run = (await (
    await request.post("/api/runs/dispatch", {
      data: { concurrency: 3, model: "stub/model", reasoning_effort: "low" },
    })
  ).json()) as { run_id: number; claims: { claim_id: string }[] };
  const [first, second] = run.claims.map((claim) => claim.claim_id);
  await request.post(`/api/runs/${String(run.run_id)}/claims/${first}`, {
    data: { status: "done", note: "Declined" },
  });
  await request.post(`/api/runs/${String(run.run_id)}/claims/${second}`, {
    data: { status: "still in progress", note: "Left in progress" },
  });
  await request.post(`/api/claims/${first}/model-calls`, {
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
    data: {
      run_id: run.run_id,
      started_on: "2026-01-01T00:00:00+00:00",
      finished_on: "2026-01-01T00:00:12+00:00",
    },
  });
  await request.post(`/api/runs/${String(run.run_id)}/finish`);

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
