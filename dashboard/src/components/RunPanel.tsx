import { Link } from "react-router";
import { formatCost, formatMoney } from "../money";
import { formatDuration } from "../time";
import type { Run } from "../types";
import { RunClaimBadge } from "./RunClaimBadge";

function Summary({ run }: Readonly<{ run: Run }>) {
  const { summary } = run;
  return (
    <section aria-label="Summary">
      <h3>Summary</h3>
      <p>
        {summary.approved} approved, {summary.declined} declined,{" "}
        {summary.referred} referred.
      </p>
      {summary.waiting_for_sign_off.map((claim) => (
        <p key={claim.claim_id}>
          {claim.claim_id}: {formatMoney(claim.payout)} waiting for sign-off.
        </p>
      ))}
      {summary.left_for_a_handler.length > 0 && (
        <p>Left for a handler: {summary.left_for_a_handler.join(", ")}.</p>
      )}
      {summary.still_in_progress.length > 0 && (
        <p>Still in progress: {summary.still_in_progress.join(", ")}.</p>
      )}
    </section>
  );
}

/** The latest run: each claim and where it stands, its cost and time, and how it ended. */
export function RunPanel({ run }: Readonly<{ run: Run }>) {
  return (
    <section aria-label="The current run">
      <h2>
        The current {run.kind} ({run.status})
      </h2>
      <p>
        {run.concurrency} at once on {run.model}, effort {run.reasoning_effort}.
        Model cost {formatCost(run.cost_nanos)}, working time{" "}
        {formatDuration(run.work_ms)}.
      </p>
      <ul>
        {run.claims.map((claim) => (
          <li key={claim.claim_id}>
            <Link className="mono" to={`/claims/${claim.claim_id}`}>
              {claim.claim_id}
            </Link>{" "}
            <RunClaimBadge status={claim.status} />
            {claim.note ? ` — ${claim.note}` : ""}
          </li>
        ))}
      </ul>
      {run.status !== "running" && <Summary run={run} />}
    </section>
  );
}
