import { formatMoney } from "../money";
import { formatTime } from "../time";
import type { Claim } from "../types";
import { DataTable } from "./DataTable";

/** The whole decision record: what was decided, on what, by whom and when. */
export function DecisionPanel({ claim }: Readonly<{ claim: Claim }>) {
  if (!claim.decision) return null;
  const paysSomething = claim.payout !== null && claim.payout > 0;
  return (
    <>
      <h2>The decision</h2>
      <p>
        {claim.decision}
        {paysSomething && claim.payout !== null
          ? `, ${formatMoney(claim.payout)}`
          : ""}
      </p>
      <p>{claim.reason}</p>
      <p>{claim.policy_reference}</p>
      <dl className="record">
        {claim.decided_by && (
          <>
            <dt>Made by</dt>
            <dd>{claim.decided_by}</dd>
          </>
        )}
        {claim.decided_on && (
          <>
            <dt>Decided</dt>
            <dd>{formatTime(claim.decided_on)}</dd>
          </>
        )}
        {claim.manual_version && (
          <>
            <dt>Claims manual</dt>
            <dd>Version {claim.manual_version}</dd>
          </>
        )}
      </dl>
      {claim.calculation && (
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
              {claim.calculation.map((line) => (
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
