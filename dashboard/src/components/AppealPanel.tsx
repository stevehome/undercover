import { hasFinalDecision } from "../appealRules";
import { formatMoney } from "../money";
import { formatTime } from "../time";
import type { Appeal, Claim } from "../types";
import { PayRedress } from "./PayRedress";
import { RecordAppealForm } from "./RecordAppealForm";
import { RecordOutcomeForm } from "./RecordOutcomeForm";
import { StatusPill } from "./StatusPill";

function Outcome({ appeal }: Readonly<{ appeal: Appeal }>) {
  const { redress, redress_payment: payment } = appeal;
  if (appeal.decided_on === null) return null;
  return (
    <>
      <h3>The ombudsman&apos;s decision</h3>
      <p>
        {appeal.status === "upheld" ? "Upheld" : "Not upheld"} on{" "}
        {appeal.decided_on}, recorded by {appeal.outcome_recorded_by ?? ""}.
      </p>
      <p className="appeal-text">{appeal.ombudsman_reason}</p>
      {redress && (
        <ul>
          <li>
            The part of the claim still owed:{" "}
            <span className="mono">{formatMoney(redress.claim_amount)}</span>
          </li>
          <li>
            Compensation for distress and inconvenience:{" "}
            <span className="mono">{formatMoney(redress.compensation)}</span>
          </li>
          <li>
            Interest:{" "}
            <span className="mono">{formatMoney(redress.interest)}</span>
          </li>
          <li>
            Redress in all:{" "}
            <span className="mono">{formatMoney(redress.total)}</span>
          </li>
        </ul>
      )}
      {payment && (
        <p>
          Paid {formatMoney(payment.amount)}, signed off by{" "}
          {payment.signed_off_by} on {formatTime(payment.paid_on)}.
        </p>
      )}
    </>
  );
}

/** A claim's appeal to the ombudsman, below its decision, and what a handler can do next. */
export function AppealPanel({
  claim,
  appeal,
  onChanged,
}: Readonly<{ claim: Claim; appeal: Appeal | null; onChanged: () => void }>) {
  if (appeal === null) {
    if (!hasFinalDecision(claim)) return null;
    return (
      <section aria-label="Appeal to the ombudsman">
        <h2>Appeal to the ombudsman</h2>
        <p>
          If the customer has taken this decision to the ombudsman, record the
          appeal here.
        </p>
        <RecordAppealForm claimId={claim.claim_id} onRecorded={onChanged} />
      </section>
    );
  }
  return (
    <section aria-label="Appeal to the ombudsman">
      <h2>
        An appeal to the ombudsman <StatusPill status={appeal.label} />
      </h2>
      <p>
        The ombudsman&apos;s reference{" "}
        <span className="mono">{appeal.ombudsman_reference}</span>, reaching us
        on {appeal.received_on}, recorded by {appeal.recorded_by}.
      </p>
      {appeal.flagged && (
        <p role="note" className="appeal-flag">
          The check found an instruction in this appeal&apos;s text:{" "}
          {appeal.flag_reason}
        </p>
      )}
      <h3>The customer&apos;s grounds</h3>
      <p className="appeal-text">{appeal.grounds}</p>
      <Outcome appeal={appeal} />
      {appeal.status === "with the ombudsman" && (
        <RecordOutcomeForm claimId={claim.claim_id} onRecorded={onChanged} />
      )}
      {appeal.status === "upheld" &&
        appeal.redress &&
        appeal.redress_payment === null && (
          <PayRedress
            claimId={claim.claim_id}
            redress={appeal.redress}
            onPaid={onChanged}
          />
        )}
    </section>
  );
}
