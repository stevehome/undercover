import { useCallback, useState } from "react";
import { Link } from "react-router";
import { fetchClaims, fetchCurrentRun } from "../api";
import { LoadError } from "../components/LoadError";
import { RunPanel } from "../components/RunPanel";
import { StartDispatch } from "../components/StartDispatch";
import { StatusBadge } from "../components/StatusBadge";
import { formatMoney } from "../money";
import type { ClaimSummary, Run } from "../types";
import { usePolling } from "../usePolling";

const TOTALS = [
  ["Waiting", "waiting"],
  ["In progress", "in progress"],
  ["Waiting for sign-off", "waiting for sign-off"],
  ["Decided", "decided"],
] as const;

export function QueuePage() {
  const [claims, setClaims] = useState<ClaimSummary[] | null>(null);

  const [run, setRun] = useState<Run | null>(null);

  const load = useCallback(
    () =>
      Promise.all([
        fetchClaims().then(setClaims),
        fetchCurrentRun().then(setRun),
      ]),
    [],
  );
  const failed = usePolling(
    load,
    run?.status === "running" ||
      (claims?.some((claim) => claim.status !== "decided") ?? true),
  );

  const count = (status: string) =>
    claims ? claims.filter((claim) => claim.status === status).length : "–";

  return (
    <main className="panel">
      <h1>The claims queue</h1>
      {failed && <LoadError />}

      <StartDispatch onStarted={() => void load()} />

      <dl className="totals">
        {TOTALS.map(([label, status]) => (
          <div key={status}>
            <dt>{label}</dt>
            <dd>{count(status)}</dd>
          </div>
        ))}
      </dl>

      {run && <RunPanel run={run} />}

      <table>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Type</th>
            <th>Summary</th>
            <th>Amount claimed</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {(claims ?? []).map((claim) => (
            <tr key={claim.claim_id}>
              <td className="mono">
                <Link to={`/claims/${claim.claim_id}`}>{claim.claim_id}</Link>
              </td>
              <td>{claim.claim_type}</td>
              <td>{claim.summary}</td>
              <td className="mono">{formatMoney(claim.amount_claimed)}</td>
              <td>
                <StatusBadge status={claim.status} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
