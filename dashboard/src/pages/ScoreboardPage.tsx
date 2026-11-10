import { useCallback, useState } from "react";
import { Link } from "react-router";
import { fetchEvaluations, startEvaluation } from "../api";
import { LoadError } from "../components/LoadError";
import { formatShare } from "../measures";
import { formatCost, formatMoney } from "../money";
import { formatDuration, formatTime } from "../time";
import type { EvalSet, Evaluation } from "../types";
import { usePolling } from "../usePolling";

const DEFAULT_CONCURRENCY = 5;
const MAX_CONCURRENCY = 25;
const SETS: [EvalSet, string][] = [
  ["evaluation", "The evaluation set"],
  ["held_out", "The held-out set"],
];

function StartEvaluation({ onStarted }: Readonly<{ onStarted: () => void }>) {
  const [concurrency, setConcurrency] = useState(DEFAULT_CONCURRENCY);
  const [evalSet, setEvalSet] = useState<EvalSet>("evaluation");
  const [tiny, setTiny] = useState(false);
  const [message, setMessage] = useState("");

  const start = () => {
    setMessage("");
    startEvaluation(concurrency, evalSet, tiny)
      .then(onStarted)
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "Could not start.");
      });
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        start();
      }}
    >
      <label>
        Claim agents at once{" "}
        <input
          type="number"
          min={1}
          max={MAX_CONCURRENCY}
          value={concurrency}
          onChange={(event) => {
            setConcurrency(Number(event.target.value));
          }}
        />
      </label>{" "}
      <label>
        Set{" "}
        <select
          value={evalSet}
          onChange={(event) => {
            setEvalSet(event.target.value as EvalSet);
          }}
        >
          {SETS.map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>{" "}
      <label>
        <input
          type="checkbox"
          checked={tiny}
          onChange={(event) => {
            setTiny(event.target.checked);
          }}
        />{" "}
        Only the 5 tiny claims
      </label>{" "}
      <button type="submit">Start an evaluation</button>
      {message && <p role="alert">{message}</p>}
    </form>
  );
}

function Row({ evaluation }: Readonly<{ evaluation: Evaluation }>) {
  const { measures } = evaluation;
  return (
    <tr>
      <td>
        <Link to={`/evaluations/${String(evaluation.run_id)}`}>
          {formatTime(evaluation.started_on)}
        </Link>
      </td>
      <td>
        {SETS.find(([value]) => value === evaluation.eval_set)?.[1]}
        {evaluation.tiny ? ", tiny" : ""}
      </td>
      <td>{evaluation.concurrency}</td>
      <td>
        {evaluation.model}, effort {evaluation.reasoning_effort}
      </td>
      <td>{evaluation.status}</td>
      <td>{formatShare(measures.decision_accuracy)}</td>
      <td>{formatShare(measures.accuracy)}</td>
      <td className="mono">{formatMoney(measures.cost_of_mistakes)}</td>
      <td>{formatShare(measures.straight_through)}</td>
      <td className="mono">
        {formatCost(measures.model_cost_per_claim_nanos)}
      </td>
      <td>{formatDuration(measures.seconds_per_claim * 1000)}</td>
      <td>
        {measures.run_seconds === null
          ? "–"
          : formatDuration(measures.run_seconds * 1000)}
      </td>
    </tr>
  );
}

export function ScoreboardPage() {
  const [evaluations, setEvaluations] = useState<Evaluation[] | null>(null);

  const load = useCallback(() => fetchEvaluations().then(setEvaluations), []);
  const failed = usePolling(
    load,
    evaluations?.some((evaluation) => evaluation.status === "running") ?? true,
  );

  return (
    <main className="panel">
      <h1>The scoreboard</h1>
      {failed && <LoadError />}

      <StartEvaluation onStarted={() => void load()} />

      <table>
        <thead>
          <tr>
            <th>Started</th>
            <th>Set</th>
            <th>At once</th>
            <th>Model</th>
            <th>Status</th>
            <th>Decision accuracy</th>
            <th>Accuracy</th>
            <th>Cost of mistakes</th>
            <th>Straight through</th>
            <th>Model cost per claim</th>
            <th>Time per claim</th>
            <th>Run time</th>
          </tr>
        </thead>
        <tbody>
          {(evaluations ?? []).map((evaluation) => (
            <Row key={evaluation.run_id} evaluation={evaluation} />
          ))}
        </tbody>
      </table>
    </main>
  );
}
