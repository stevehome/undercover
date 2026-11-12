import { useCallback, useState } from "react";
import { Link, useParams } from "react-router";
import { fetchEvaluation } from "../api";
import { DataTable } from "../components/DataTable";
import { LoadError } from "../components/LoadError";
import { StatusPill } from "../components/StatusPill";
import { Loading } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { describeAnswer, formatGrade, formatShare } from "../measures";
import { formatCost, formatMoney } from "../money";
import { formatDuration } from "../time";
import type { ClaimGrade, Evaluation } from "../types";
import { usePolling } from "../usePolling";

const yesNo = (matched: boolean) => (matched ? "Yes" : "No");

/** A claim's letter and score and the judge's two checks, as yes or no. */
function GradeCells({ grade }: Readonly<{ grade: ClaimGrade | null }>) {
  if (grade === null) return <td colSpan={3}>Not graded</td>;
  return (
    <>
      <td>
        {grade.letter} ({grade.score.toFixed(2)})
      </td>
      <td>{yesNo(grade.same_grounds_matched)}</td>
      <td>{yesNo(grade.same_section_matched)}</td>
    </>
  );
}

export function EvaluationPage() {
  const { runId } = useParams<{ runId: string }>();
  const [evaluation, setEvaluation] = useState<Evaluation | null>(null);

  const load = useCallback(
    () => fetchEvaluation(runId ?? "").then(setEvaluation),
    [runId],
  );
  const failed = usePolling(load, evaluation?.status !== "finished");

  if (!evaluation) {
    return (
      <main className="panel">{failed ? <LoadError /> : <Loading />}</main>
    );
  }
  const { measures } = evaluation;

  return (
    <main className="panel">
      <PageHeader title={`Evaluation ${String(evaluation.run_id)}`}>
        Each claim with the handler's answer beside the agent's, and the judge's
        grade.
      </PageHeader>
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
        <div>
          <dt>Grade (0 to 3)</dt>
          <dd>{formatGrade(measures.grade)}</dd>
        </div>
        <div>
          <dt>Judge cost</dt>
          <dd>{formatCost(measures.judge_cost_nanos)}</dd>
        </div>
      </dl>

      <DataTable>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Handler</th>
            <th>Agent</th>
            <th>Result</th>
            <th className="number">Cost of mistake</th>
            <th>Grade</th>
            <th>Same grounds</th>
            <th>Same section</th>
            <th className="number">Model cost</th>
            <th className="number">Judge cost</th>
            <th className="number">Time</th>
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
              <td>
                <StatusPill status={claim.right ? "Right" : "Miss"} />
              </td>
              <td className="number mono">{formatMoney(claim.mistake_cost)}</td>
              <GradeCells grade={claim.grade} />
              <td className="number mono">{formatCost(claim.cost_nanos)}</td>
              <td className="number mono">
                {formatCost(claim.judge_cost_nanos)}
              </td>
              <td className="number">{formatDuration(claim.work_ms)}</td>
            </tr>
          ))}
        </tbody>
      </DataTable>
    </main>
  );
}
