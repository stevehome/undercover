import { toWireAmount } from "./money";
import type { Claim, ClaimSummary } from "./types";

export type FetchInput = string | URL | Request;

export function requestUrl(input: FetchInput): string {
  if (typeof input === "string") return input;
  if (input instanceof URL) return input.toString();
  return input.url;
}

/** Serve a claim as the API does: amounts as two-decimal strings. */
export function claimToWire(claim: Claim) {
  return {
    ...claim,
    amount_claimed: toWireAmount(claim.amount_claimed),
    items: claim.items.map((item) => ({
      ...item,
      amount: toWireAmount(item.amount),
    })),
    payout: claim.payout === null ? null : toWireAmount(claim.payout),
    paid_amount:
      claim.paid_amount === null ? null : toWireAmount(claim.paid_amount),
  };
}

export function summaryToWire(summary: ClaimSummary) {
  return { ...summary, amount_claimed: toWireAmount(summary.amount_claimed) };
}

/** An evaluation as the API serves it: held-out, tiny, one hit and one miss. */
export const wireEvaluation = {
  run_id: 7,
  kind: "evaluation",
  status: "finished",
  eval_set: "held_out",
  tiny: true,
  concurrency: 5,
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
  started_on: "2026-01-01T00:00:00+00:00",
  finished_on: "2026-01-01T00:00:30+00:00",
  measures: {
    decision_accuracy: "0.8000",
    accuracy: "0.6000",
    straight_through: "0.6000",
    cost_of_mistakes: "1550.00",
    model_cost_per_claim: "0.000624000",
    seconds_per_claim: "27.900",
    run_seconds: "30.000",
  },
  claims: [
    {
      claim_id: "EVAL-7-CLM-1101",
      source_claim_id: "CLM-1101",
      status: "done",
      note: "Approved $580.00",
      handler_decision: "approve",
      handler_payout: "580.00",
      agent_decision: "approve",
      agent_payout: "580.00",
      reason: "Covered.",
      right: true,
      mistake_cost: "0.00",
      cost: "0.000624000",
      work_ms: 27900,
    },
    {
      claim_id: "EVAL-7-CLM-1102",
      source_claim_id: "CLM-1102",
      status: "done",
      note: "Declined",
      handler_decision: "approve",
      handler_payout: "250.00",
      agent_decision: "decline",
      agent_payout: "0.00",
      reason: "Not covered.",
      right: false,
      mistake_cost: "1500.00",
      cost: "0.000624000",
      work_ms: 10000,
    },
  ],
};
