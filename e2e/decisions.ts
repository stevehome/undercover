import type { APIRequestContext } from "@playwright/test";
import { agentHeaders } from "./agentKey";

interface Decision {
  decision: "approve" | "decline" | "refer";
  payout: string;
  reason: string;
  policy_reference: string;
}

const PROBE_CENTS = 100000;

const toCents = (dollars: string) => Math.round(Number(dollars) * 100);
const toDollars = (cents: number) => (cents / 100).toFixed(2);

/** A request to work out one expense line under emergency medical. */
function expense(cents: number) {
  return {
    benefit: "emergency_medical",
    lines: [
      {
        description: "Expense",
        amount: toDollars(cents),
        quantity: 1,
        kind: "expense",
        nights: 0,
        hours: 0,
      },
    ],
    paid_by_others: "0.00",
  };
}

/**
 * Record a decision as the agent does: an approval's calculation first, then the
 * decision with its maker (claims manual section 14). The calculation is one
 * expense for the payout plus the plan's deductible, which a first calculation of
 * a larger amount shows.
 */
export async function recordDecision(
  request: APIRequestContext,
  claimId: string,
  decision: Decision,
) {
  if (decision.decision === "approve") {
    const url = `/api/claims/${claimId}/payout`;
    const probe = await request.post(url, {
      headers: agentHeaders,
      data: expense(PROBE_CENTS),
    });
    const { payout } = (await probe.json()) as { payout: string };
    const deductible = PROBE_CENTS - toCents(payout);
    await request.post(url, {
      headers: agentHeaders,
      data: expense(toCents(decision.payout) + deductible),
    });
  }
  return request.post(`/api/claims/${claimId}/decision`, {
    headers: agentHeaders,
    data: { ...decision, decided_by: "The end-to-end test" },
  });
}
