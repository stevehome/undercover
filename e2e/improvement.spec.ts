import { expect, test as unsigned } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";
import { signIn, test } from "./signIn";
import { agentHeaders } from "./agentKey";
import { askedFor, startRound } from "./startedWork";

const CHANGE = {
  instructions: "Decide the claim, and never approve a late one.\n",
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
};

/** A round played out through the backend's operations, as the agent's service does. */
class PlayedRound {
  constructor(
    private readonly request: APIRequestContext,
    readonly roundId: number,
    readonly runId: number,
  ) {}

  static async start(request: APIRequestContext) {
    const { roundId, runId } = await startRound(request);
    return new PlayedRound(request, roundId, runId);
  }

  async stage(stage: string, progress: number) {
    await this.request.post(
      `/api/improver/rounds/${String(this.roundId)}/stage`,
      {
        headers: agentHeaders,
        data: { stage, progress },
      },
    );
  }

  /** The improver proposes a change and the stretch ends, so the round waits. */
  async propose() {
    const proposal = await this.request.post(
      `/api/improver/rounds/${String(this.roundId)}/proposals`,
      {
        headers: agentHeaders,
        data: {
          kind: "change",
          content: CHANGE,
          reason: "Late claims were approved.",
        },
      },
    );
    await this.endStretch();
    return ((await proposal.json()) as { proposal_id: number }).proposal_id;
  }

  /** Let go of the one-run rule, so the other specs' runs are not refused. */
  async endStretch() {
    await this.request.post(`/api/runs/${String(this.runId)}/finish`, {
      headers: agentHeaders,
    });
  }

  async finish() {
    await this.stage("finished", 0);
  }
}

test("the page shows each stage of a round as it happens", async ({
  page,
  request,
}) => {
  const round = await PlayedRound.start(request);
  await page.goto("/improvement");
  const current = page.locator("[aria-current=step]");

  for (const [stage, progress, label] of [
    ["first evaluations", 1, "First evaluations, 1 of 3"],
    ["first evaluations", 3, "First evaluations, 3 of 3"],
    ["improver working", 0, "The improver is working"],
    ["evaluations", 2, "Evaluations, 2 of 3"],
    ["verdict", 0, "Verdict"],
    ["recipe waiting", 0, "A recipe is waiting for approval"],
  ] as const) {
    await round.stage(stage, progress);
    await expect(current).toHaveText(label);
  }

  await round.finish();
  await expect(current).toHaveCount(0);
  await round.endStretch();
  await expect(
    page.getByRole("row", { name: /Dana Whitfield/ }).first(),
  ).toContainText("finished");
});

test("a proposal waiting shows its diff, and approving it is recorded and the agent is asked to carry the round on", async ({
  page,
  request,
}) => {
  const round = await PlayedRound.start(request);
  const proposalId = await round.propose();
  await page.goto("/improvement");

  await expect(
    page.getByRole("heading", { name: "A change is waiting for approval" }),
  ).toBeVisible();
  await expect(
    page.getByText("Decide the claim, and never approve a late one."),
  ).toBeVisible();
  await expect(
    page.getByText(/proposed openai\/gpt-6-luna at low/),
  ).toBeVisible();

  await page.getByRole("button", { name: "Approve" }).click();
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "Approve" })
    .click();

  await expect
    .poll(() => askedFor(request, "carry_round_on"))
    .toContainEqual({ round_id: round.roundId, proposal_id: proposalId });
  const proposal = (await (
    await request.get(`/api/proposals/${String(proposalId)}`, {
      headers: agentHeaders,
    })
  ).json()) as { status: string; decided_by: string };
  expect(proposal).toMatchObject({
    status: "approved",
    decided_by: "Dana Whitfield",
  });
  await round.finish();
});

unsigned(
  "a handler who can't approve sees why and has no buttons",
  async ({ page, request }) => {
    const round = await PlayedRound.start(request);
    await round.propose();
    await signIn(page, "marcus.oyelaran");

    await page.goto("/improvement");

    await expect(
      page.getByText(/Marcus Oyelaran can't approve or reject this/),
    ).toBeVisible();
    await expect(page.getByRole("button", { name: "Approve" })).toHaveCount(0);
    await expect(
      page.getByRole("button", { name: "Start a round" }),
    ).toHaveCount(0);
    await round.finish();
  },
);
