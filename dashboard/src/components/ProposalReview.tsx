import { useState } from "react";
import { decideProposal } from "../api";
import type { Proposal } from "../types";
import { ConfirmDialog } from "./ConfirmDialog";
import { DiffView } from "./DiffView";

function consequence(
  asking: "approve" | "reject",
  isChange: boolean,
  reason: string,
): string {
  if (asking === "reject") return `The improver is told: ${reason}`;
  return isChange
    ? "This saves a new version of the claim agent's configuration, which the improver then has evaluated."
    : "This saves a new version of the improver's recipe.";
}

/** A proposal waiting for a handler: what it changes, and approve or reject it. */
export function ProposalReview({
  proposal,
  handlerName,
  canDecide,
  onDecided,
}: Readonly<{
  proposal: Proposal;
  handlerName: string;
  canDecide: boolean;
  onDecided: () => void;
}>) {
  const [asking, setAsking] = useState<"approve" | "reject" | null>(null);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const isChange = proposal.kind === "change";

  const send = () => {
    if (asking === null) return;
    setMessage("");
    decideProposal(proposal.proposal_id, asking, reason)
      .then(onDecided)
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "Could not send.");
      });
    setAsking(null);
  };

  return (
    <section aria-label="Proposal waiting for approval">
      <h2>
        {isChange
          ? "A change is waiting for approval"
          : "A new recipe is waiting for approval"}
      </h2>
      <p>The improver's reason: {proposal.reason}</p>
      {isChange && (
        <p>
          Model and reasoning effort: {proposal.model_before} at{" "}
          {proposal.reasoning_effort_before}, proposed {proposal.model_after} at{" "}
          {proposal.reasoning_effort_after}.
        </p>
      )}
      <DiffView lines={proposal.lines} />
      {message && <p role="alert">{message}</p>}
      {canDecide ? (
        <div>
          <label>
            Why you are rejecting it (the improver reads this)
            <textarea
              value={reason}
              onChange={(event) => {
                setReason(event.target.value);
              }}
            />
          </label>
          <div className="actions">
            <button
              type="button"
              onClick={() => {
                setAsking("approve");
              }}
            >
              Approve
            </button>
            <button
              type="button"
              className="secondary"
              disabled={reason.trim() === ""}
              onClick={() => {
                setAsking("reject");
              }}
            >
              Reject
            </button>
          </div>
        </div>
      ) : (
        <p>
          {handlerName} can't approve or reject this: only a handler who can
          sign off payouts over the limit can.
        </p>
      )}
      {asking && (
        <ConfirmDialog
          title={asking === "approve" ? "Approve this?" : "Reject this?"}
          confirmLabel={asking === "approve" ? "Approve" : "Reject"}
          onConfirm={send}
          onCancel={() => {
            setAsking(null);
          }}
        >
          <p>{consequence(asking, isChange, reason)}</p>
        </ConfirmDialog>
      )}
    </section>
  );
}
