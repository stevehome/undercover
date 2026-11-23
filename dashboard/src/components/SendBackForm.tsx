import { useState } from "react";
import { sendBackClaim } from "../api";
import { ConfirmDialog } from "./ConfirmDialog";

export const MAX_NOTE_LENGTH = 1000;

/** A senior handler's note to the agent, sent with the decision on a confirmation. */
export function SendBackForm({
  claimId,
  onUpdated,
}: Readonly<{ claimId: string; onUpdated: () => void }>) {
  const [note, setNote] = useState("");
  const [asking, setAsking] = useState(false);
  const [message, setMessage] = useState("");

  const send = () => {
    setAsking(false);
    setMessage("");
    sendBackClaim(claimId, note.trim())
      .then(onUpdated)
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "Could not send.");
      });
  };

  return (
    <div>
      <label>
        A note for the agent, to send the decision back
        <textarea
          value={note}
          maxLength={MAX_NOTE_LENGTH}
          onChange={(event) => {
            setNote(event.target.value);
          }}
        />
      </label>
      {message && <p role="alert">{message}</p>}
      <button
        type="button"
        className="secondary"
        disabled={note.trim() === ""}
        onClick={() => {
          setAsking(true);
        }}
      >
        Send back
      </button>
      {asking && (
        <ConfirmDialog
          title={`Send ${claimId} back to the agent?`}
          confirmLabel="Send back"
          onConfirm={send}
          onCancel={() => {
            setAsking(false);
          }}
        >
          <p>The agent reads this note and decides the claim again:</p>
          <p>{note.trim()}</p>
        </ConfirmDialog>
      )}
    </div>
  );
}
