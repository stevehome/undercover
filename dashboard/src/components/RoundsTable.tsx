import { formatGrade, formatShare } from "../measures";
import { formatCost, formatMoney } from "../money";
import { formatTime } from "../time";
import type { Round, Scores } from "../types";
import { DataTable } from "./DataTable";
import { EmptyState } from "./EmptyState";
import { StatusPill } from "./StatusPill";

const before = (scores: Scores | null, after: Scores | null) =>
  scores && after
    ? `${formatShare(scores.accuracy ?? 0)} to ${formatShare(after.accuracy ?? 0)}`
    : "–";

const grades = (scores: Scores | null, after: Scores | null) =>
  scores && after
    ? `${formatGrade(scores.grade)} to ${formatGrade(after.grade)}`
    : "–";

function decisions(round: Round): string {
  const made = round.proposals
    .filter((proposal) => proposal.decided_by !== null)
    .map(
      (proposal) =>
        `${proposal.kind} ${proposal.status} by ${proposal.decided_by ?? ""}`,
    );
  return made.length === 0 ? "–" : made.join("; ");
}

/** The rounds so far, newest first, with what each tried and what came of it. */
export function RoundsTable({ rounds }: Readonly<{ rounds: Round[] }>) {
  if (rounds.length === 0) {
    return (
      <EmptyState>
        No rounds yet. Start one to see what the improver finds.
      </EmptyState>
    );
  }
  return (
    <DataTable>
      <thead>
        <tr>
          <th className="number">Round</th>
          <th>Started</th>
          <th className="number">Recipe</th>
          <th>Settings</th>
          <th className="number">Version tried</th>
          <th>Reason</th>
          <th className="number">Held-out accuracy</th>
          <th className="number">Held-out grade</th>
          <th>Verdict</th>
          <th>Approved or rejected</th>
          <th className="number">Cost</th>
        </tr>
      </thead>
      <tbody>
        {rounds.map((round) => (
          <tr key={round.round_id}>
            <td className="number">{round.round_id}</td>
            <td>
              {round.started_by_name}, {formatTime(round.started_on)}
            </td>
            <td className="number">{round.recipe_version}</td>
            <td>
              Limit {formatMoney(round.spending_limit)},{" "}
              {round.settings.improver_agents_at_once} at once
            </td>
            <td className="number">{round.configuration_version ?? "–"}</td>
            <td>{round.improver_reason ?? "–"}</td>
            <td className="number">
              {before(round.held_out_before, round.held_out_after)}
            </td>
            <td className="number">
              {grades(round.held_out_before, round.held_out_after)}
            </td>
            <td>
              {round.verdict ? (
                <>
                  <StatusPill status={round.verdict} /> {round.verdict_reason}
                </>
              ) : (
                <StatusPill status={round.stage} />
              )}
            </td>
            <td>{decisions(round)}</td>
            <td className="number mono">{formatCost(round.cost_nanos)}</td>
          </tr>
        ))}
      </tbody>
    </DataTable>
  );
}
