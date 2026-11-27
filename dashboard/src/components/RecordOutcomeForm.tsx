import { useState } from "react";
import { recordAppealOutcome } from "../appealsApi";
import { parseTypedAmount } from "../money";
import type { NewOutcome } from "../types";
import { MAX_TEXT_LENGTH } from "./RecordAppealForm";

type Outcome = NewOutcome["outcome"];
const PARTS = [
  ["claim_amount", "The part of the claim still owed"],
  ["compensation", "Compensation for distress and inconvenience"],
  ["interest", "Interest"],
] as const;

/** Record the ombudsman's decision on an appeal, with the redress when it is upheld. */
export function RecordOutcomeForm({
  claimId,
  onRecorded,
}: Readonly<{ claimId: string; onRecorded: () => void }>) {
  const [outcome, setOutcome] = useState<Outcome>("upheld");
  const [decidedOn, setDecidedOn] = useState("");
  const [reason, setReason] = useState("");
  const [typed, setTyped] = useState({
    claim_amount: "",
    compensation: "",
    interest: "",
  });
  const [message, setMessage] = useState("");

  const upheld = outcome === "upheld";
  const cents = PARTS.map(([part]) => parseTypedAmount(typed[part]) ?? 0);
  const typedOk = PARTS.every(
    ([part]) => typed[part] === "" || parseTypedAmount(typed[part]) !== null,
  );
  const total = cents.reduce((sum, amount) => sum + amount, 0);
  const ready =
    decidedOn !== "" &&
    reason.trim() !== "" &&
    (!upheld || (typedOk && total > 0));

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        setMessage("");
        const [claimAmount = 0, compensation = 0, interest = 0] = upheld
          ? cents
          : [];
        recordAppealOutcome(claimId, {
          outcome,
          decided_on: decidedOn,
          reason: reason.trim(),
          claim_amount: claimAmount,
          compensation,
          interest,
        })
          .then(onRecorded)
          .catch((error: unknown) => {
            setMessage(
              error instanceof Error ? error.message : "Could not record.",
            );
          });
      }}
    >
      <label>
        The ombudsman&apos;s decision
        <select
          value={outcome}
          onChange={(event) => {
            setOutcome(event.target.value as Outcome);
          }}
        >
          <option value="upheld">Upheld</option>
          <option value="not upheld">Not upheld</option>
        </select>
      </label>
      <label>
        The date of the decision
        <input
          type="date"
          value={decidedOn}
          onChange={(event) => {
            setDecidedOn(event.target.value);
          }}
        />
      </label>
      <label className="wide">
        The ombudsman&apos;s reason
        <textarea
          value={reason}
          maxLength={MAX_TEXT_LENGTH}
          onChange={(event) => {
            setReason(event.target.value);
          }}
        />
      </label>
      {upheld &&
        PARTS.map(([part, label]) => (
          <label key={part}>
            {label}, in dollars
            <input
              className="number"
              inputMode="decimal"
              value={typed[part]}
              onChange={(event) => {
                setTyped({ ...typed, [part]: event.target.value });
              }}
            />
          </label>
        ))}
      {upheld && !ready && decidedOn !== "" && reason.trim() !== "" && (
        <p>
          An upheld appeal needs redress: the three amounts, written like
          120.00, must come to more than zero.
        </p>
      )}
      {message && <p role="alert">{message}</p>}
      <button type="submit" disabled={!ready}>
        Record the decision
      </button>
    </form>
  );
}
