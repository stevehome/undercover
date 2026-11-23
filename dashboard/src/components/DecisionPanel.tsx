import { useEffect, useState } from "react";
import { fetchHandlers } from "../api";
import { formatMoney } from "../money";
import { formatTime } from "../time";
import type { CalculationLine, Claim, Decision, Handler } from "../types";
import { DataTable } from "./DataTable";

interface Recorded {
  decision: Decision;
  payout: number | null;
  reason: string | null;
  policy_reference: string | null;
  decided_by: string | null;
  decided_on: string | null;
  manual_version: string | null;
  calculation: CalculationLine[] | null;
}

/** One decision as recorded: what was decided, on what, by whom and when. */
function RecordedDecision({ record }: Readonly<{ record: Recorded }>) {
  const paysSomething = record.payout !== null && record.payout > 0;
  return (
    <>
      <p>
        {record.decision}
        {paysSomething && record.payout !== null
          ? `, ${formatMoney(record.payout)}`
          : ""}
      </p>
      <p>{record.reason}</p>
      <p>{record.policy_reference}</p>
      <dl className="record">
        {record.decided_by && (
          <>
            <dt>Made by</dt>
            <dd>{record.decided_by}</dd>
          </>
        )}
        {record.decided_on && (
          <>
            <dt>Decided</dt>
            <dd>{formatTime(record.decided_on)}</dd>
          </>
        )}
        {record.manual_version && (
          <>
            <dt>Claims manual</dt>
            <dd>Version {record.manual_version}</dd>
          </>
        )}
      </dl>
      {record.calculation && (
        <>
          <h3>How the payout was worked out</h3>
          <DataTable>
            <thead>
              <tr>
                <th>Line</th>
                <th className="number">Amount</th>
              </tr>
            </thead>
            <tbody>
              {record.calculation.map((line) => (
                <tr key={line.step}>
                  <td>{line.step}</td>
                  <td className="number mono">{formatMoney(line.amount)}</td>
                </tr>
              ))}
            </tbody>
          </DataTable>
        </>
      )}
    </>
  );
}

/** The decisions a senior handler sent back, each with their note, then the current one. */
export function DecisionPanel({ claim }: Readonly<{ claim: Claim }>) {
  const sentBack = claim.sent_back_decisions;
  const [handlers, setHandlers] = useState<Handler[]>([]);
  useEffect(() => {
    if (sentBack.length > 0) void fetchHandlers().then(setHandlers);
  }, [sentBack.length]);
  const nameOf = (id: string) =>
    handlers.find((handler) => handler.handler_id === id)?.name ?? id;
  return (
    <>
      {sentBack.map((sent, index) => (
        <section key={sent.sent_back_on} aria-label="A decision sent back">
          <h2>
            {sentBack.length > 1
              ? `A decision sent back (${String(index + 1)})`
              : "A decision sent back"}
          </h2>
          <RecordedDecision record={sent} />
          <p>
            Sent back by {nameOf(sent.sent_back_by)} on{" "}
            {formatTime(sent.sent_back_on)}: {sent.note}
          </p>
        </section>
      ))}
      {claim.decision && (
        <>
          <h2>The decision</h2>
          <RecordedDecision record={{ ...claim, decision: claim.decision }} />
        </>
      )}
      {claim.status === "sent back" && (
        <p>
          This claim was sent back with a note. The agent will decide it again
          at the next dispatch.
        </p>
      )}
    </>
  );
}
