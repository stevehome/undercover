import { useCallback, useState } from "react";
import { Link } from "react-router";
import { fetchAppealFigures, fetchAppeals } from "../appealsApi";
import { AppealFigures } from "../components/AppealFigures";
import { DataTable } from "../components/DataTable";
import { EmptyState } from "../components/EmptyState";
import { LoadError } from "../components/LoadError";
import { Loading } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { StatusPill } from "../components/StatusPill";
import { formatMoney } from "../money";
import type { Appeal, AppealFigures as Figures, AppealStatus } from "../types";
import { usePolling } from "../usePolling";

const STATUSES: ("all" | AppealStatus)[] = [
  "all",
  "with the ombudsman",
  "upheld",
  "not upheld",
];

function Row({ appeal }: Readonly<{ appeal: Appeal }>) {
  const { claim } = appeal;
  return (
    <tr>
      <td>
        <Link to={`/claims/${appeal.claim_id}`} className="mono">
          {appeal.claim_id}
        </Link>
      </td>
      <td>{claim.customer.name}</td>
      <td>{claim.plan}</td>
      <td>
        {claim.decision}
        {claim.payout !== null && claim.payout > 0
          ? `, ${formatMoney(claim.payout)}`
          : ""}
      </td>
      <td>{appeal.received_on}</td>
      <td>
        <StatusPill status={appeal.label} />
      </td>
      <td>{appeal.decided_on ?? "–"}</td>
      <td className="number mono">
        {appeal.redress ? formatMoney(appeal.redress.total) : "–"}
      </td>
    </tr>
  );
}

/** Every appeal to the ombudsman, with how they stand and what the redress comes to. */
export function AppealsPage() {
  const [appeals, setAppeals] = useState<Appeal[] | null>(null);
  const [figures, setFigures] = useState<Figures | null>(null);
  const [status, setStatus] = useState<"all" | AppealStatus>("all");

  const load = useCallback(
    () =>
      Promise.all([
        fetchAppeals().then(setAppeals),
        fetchAppealFigures().then(setFigures),
      ]),
    [],
  );
  const failed = usePolling(load, false);

  if (appeals === null || figures === null) {
    return (
      <main className="panel">{failed ? <LoadError /> : <Loading />}</main>
    );
  }
  const shown = appeals.filter((a) => status === "all" || a.status === status);

  return (
    <main className="panel wide">
      <PageHeader title="Appeals to the ombudsman">
        Customers who took a final decision to the ombudsman, how each stands,
        and the redress we owe or have paid.
      </PageHeader>
      {failed && <LoadError />}
      <AppealFigures figures={figures} />

      <form>
        <label>
          Show{" "}
          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value as "all" | AppealStatus);
            }}
          >
            {STATUSES.map((value) => (
              <option key={value} value={value}>
                {value === "all" ? "All appeals" : value}
              </option>
            ))}
          </select>
        </label>
      </form>

      <DataTable>
        <thead>
          <tr>
            <th>Claim</th>
            <th>Customer</th>
            <th>Plan</th>
            <th>Our decision</th>
            <th>Received</th>
            <th>Appeal</th>
            <th>Decided</th>
            <th className="number">Redress</th>
          </tr>
        </thead>
        <tbody>
          {shown.map((appeal) => (
            <Row key={appeal.claim_id} appeal={appeal} />
          ))}
        </tbody>
      </DataTable>
      {appeals.length === 0 && (
        <EmptyState>
          No appeals yet. Open a decided claim and record one from its page.
        </EmptyState>
      )}
      {appeals.length > 0 && shown.length === 0 && (
        <EmptyState>No appeals have this status.</EmptyState>
      )}
    </main>
  );
}
