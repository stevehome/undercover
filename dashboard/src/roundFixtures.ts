/** A round as the API serves it, for the tests of the pages that show rounds. */
export const wireScores = (accuracy: string, grade: string | null) => ({
  runs: 2,
  accuracy,
  grade,
  cost_per_claim: "0.000100000",
  seconds_per_claim: "10.000",
});

export const wireProposal = {
  proposal_id: 3,
  round_id: 2,
  kind: "change",
  status: "pending",
  reason: "Late claims were approved.",
  created_on: "2026-01-01T00:00:00+00:00",
  decided_by: null,
  decided_on: null,
  rejection_reason: null,
  version: null,
  from_version: 1,
  lines: [
    { kind: "removed", text: "Decide the claim." },
    { kind: "added", text: "Decide the claim, and never approve a late one." },
  ],
  model_before: "openai/gpt-6-luna",
  model_after: "openai/gpt-6-luna",
  reasoning_effort_before: "low",
  reasoning_effort_after: "medium",
};

const base = {
  progress: 0,
  recipe_version: 1,
  settings: { improver_agents_at_once: "25", round_spending_limit: "0.50" },
  started_by_name: "Dana Whitfield",
  started_on: "2026-01-01T09:00:00+00:00",
  finished_on: null,
  configuration_version: null,
  improver_reason: null,
  held_out_before: null,
  held_out_after: null,
  verdict: null,
  verdict_reason: null,
  cost: "0.012300000",
  spending_limit: "0.50",
  proposals: [],
};

export const wireRound = (overrides: Record<string, unknown>) => ({
  round_id: 2,
  stage: "improver working",
  ...base,
  ...overrides,
});

export const finishedRound = wireRound({
  round_id: 1,
  stage: "finished",
  configuration_version: 2,
  improver_reason: "Add a rule for late claims.",
  held_out_before: wireScores("0.7200", "1.400"),
  held_out_after: wireScores("0.8400", "1.700"),
  verdict: "kept",
  verdict_reason: "accuracy improved",
  proposals: [
    {
      ...wireProposal,
      round_id: 1,
      status: "approved",
      decided_by: "Dana Whitfield",
    },
  ],
});
