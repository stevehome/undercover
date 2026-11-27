import { useState } from "react";
import { recordAppeal } from "../appealsApi";

export const MAX_TEXT_LENGTH = 2000;

/** Record an appeal to the ombudsman against a claim, from the ombudsman's letter. */
export function RecordAppealForm({
  claimId,
  onRecorded,
}: Readonly<{ claimId: string; onRecorded: () => void }>) {
  const [reference, setReference] = useState("");
  const [receivedOn, setReceivedOn] = useState("");
  const [grounds, setGrounds] = useState("");
  const [message, setMessage] = useState("");
  const ready =
    reference.trim() !== "" && receivedOn !== "" && grounds.trim() !== "";

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        setMessage("");
        recordAppeal(claimId, {
          ombudsman_reference: reference.trim(),
          received_on: receivedOn,
          grounds: grounds.trim(),
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
        The ombudsman&apos;s reference
        <input
          value={reference}
          maxLength={100}
          onChange={(event) => {
            setReference(event.target.value);
          }}
        />
      </label>
      <label>
        The date it reached us
        <input
          type="date"
          value={receivedOn}
          onChange={(event) => {
            setReceivedOn(event.target.value);
          }}
        />
      </label>
      <label className="wide">
        The customer&apos;s grounds, in their own words
        <textarea
          value={grounds}
          maxLength={MAX_TEXT_LENGTH}
          onChange={(event) => {
            setGrounds(event.target.value);
          }}
        />
      </label>
      {message && <p role="alert">{message}</p>}
      <button type="submit" disabled={!ready}>
        Record the appeal
      </button>
    </form>
  );
}
