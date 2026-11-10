import { useCallback, useState } from "react";
import { Link, useParams } from "react-router";
import { fetchEvaluation } from "../api";
import { LoadError } from "../components/LoadError";
import { describeAnswer, formatShare } from "../measures";
import { formatCost, formatMoney } from "../money";
import { formatDuration } from "../time";
import type { Evaluation } from "../types";
import { usePolling } from "../usePolling";

export function EvaluationPage() {
  const { runId } = useParams<{ runId: string }>();
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);

  const load = useCallback(
    () => fetchEvaluation(runId ?? "").then(setEvaluation),
    [runId],
  );
  const failed = usePolling(load, evaluation?.status !== "finished");

  if (!evaluation) {
    return <main className="panel">{failed ? <LoadError /> : "Loading…"}</main>;
  }
  const { measures } = evaluation;

  return (
    <main className="panel">
      <h1>Evaluation {evaluation.run_id}</h1>
      {failed && <LoadError />}
      <p>
        {evaluation.eval_set === "held_out"
          ? "The held-out set"
          : "The evaluation set"}
        {evaluation.tiny ? ", tiny claims only" : ""}, {evaluation.concurrency}{" "}
        at once on {evaluation.model}, effort {evaluation.reasoning_effort}.
        Status: {evaluation.status}.
      </p>
      <dl className="totals">
        <div>
          <dt>Decision accuracy</dt>
          <dd>{formatShare(measures.decision_accuracy)}</dd>
        </div>
        <div>
          <dt>Accuracy</dt>
          <dd>{formatShare(measures.accuracy)}</dd>
        </div>
        <div>
          <dt>Cost of mistakes</dt>
          <dd>{formatMoney(measures.cost_of_mistakes)}</dd>
        </div>
        <div>
          <dt>Straight through</dt>
          <dd>{formatShare(measures.straight_through)}</dd>
        </div>
      </dl>

      <table>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Handler</th>
            <th>Agent</th>
            <th>Result</th>
            <th>Cost of mistake</th>
            <th>Model cost</th>
            <th>Time</th>
          </tr>
        </thead>
        <tbody>
          {evaluation.claims.map((claim) => (
            <tr key={claim.claim_id} className={claim.right ? "" : "miss"}>
              <td className="mono">
                <Link to={`/claims/${claim.claim_id}`}>
                  {claim.source_claim_id}
                </Link>
              </td>
              <td>
                {describeAnswer(claim.handler_decision, claim.handler_payout)}
              </td>
              <td>
                {describeAnswer(claim.agent_decision, claim.agent_payout)}
              </td>
              <td>{claim.right ? "Right" : "Miss"}</td>
              <td className="mono">{formatMoney(claim.mistake_cost)}</td>
              <td className="mono">{formatCost(claim.cost_nanos)}</td>
              <td>{formatDuration(claim.work_ms)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </main>
  );
}
