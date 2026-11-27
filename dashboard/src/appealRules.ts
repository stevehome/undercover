import type { Claim } from "./types";

/** Whether a claim's decision is final, so it can be appealed: approved and paid, or declined. */
export function hasFinalDecision(claim: Claim): boolean {
  if (claim.evaluation_run_id !== null || claim.status !== "decided") {
    return false;
  }
  return (
    claim.decision === "decline" ||
    (claim.decision === "approve" && claim.paid_amount !== null)
  );
}
