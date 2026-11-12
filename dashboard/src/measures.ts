import { formatMoney } from "./money";
import type { Decision } from "./types";

/** Format a share from 0 to 1 as a percentage, such as "96.0%". */
export const formatShare = (share: number) => `${(share * 100).toFixed(1)}%`;

/** Format the judge's grade from 0 to 3, or say there is none. */
export const formatGrade = (grade: number | null) =>
  grade === null ? "Not graded" : grade.toFixed(2);

/** Describe an answer for people, such as "approve, $420.00" or "refer". */
export function describeAnswer(
  decision: Decision | null,
  payout: number | null,
): string {
  if (decision === null) return "no decision";
  if (decision !== "approve" || payout === null) return decision;
  return `${decision}, ${formatMoney(payout)}`;
}
