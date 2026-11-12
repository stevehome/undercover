import { useEffect, useState } from "react";
import { fetchHandlers, signOffClaim } from "../api";
import { formatMoney } from "../money";
import { formatTime } from "../time";
import type { Claim, Handler } from "../types";
import { useMe } from "../useMe";

function SignOff({
  claimId,
  onUpdated,
}: Readonly<{ claimId: string; onUpdated: () => void }>) {
  const me = useMe();
  if (me?.can_approve_over_limit) {
    return (
      <button
        onClick={() => {
          void signOffClaim(claimId).then(onUpdated);
        }}
        type="button"
      >
        Sign off as {me.name}
      </button>
    );
  }
  return (
    <p>
      {me?.name ?? "You"} can't sign off this payout: only a handler who can
      sign off payouts over the limit can.
    </p>
  );
}

export function PaymentPanel({
  claim,
  onUpdated,
}: Readonly<{ claim: Claim; onUpdated: () => void }>) {
  const [handlers, setHandlers] = useState<Handler[]>([]);
  const waiting = claim.status === "waiting for sign-off";
  const signedOffBy = claim.signed_off_by;

  useEffect(() => {
    if (waiting || signedOffBy !== null) void fetchHandlers().then(setHandlers);
  }, [waiting, signedOffBy]);

  if (waiting && claim.evaluation_run_id !== null) {
    return (
      <section>
        <p>This is a copy for an evaluation, so it is never signed off.</p>
      </section>
    );
  }

  if (waiting) {
    return (
      <section>
        <h2>Sign off</h2>
        <p>This payout is over the approval limit.</p>
        <SignOff claimId={claim.claim_id} onUpdated={onUpdated} />
      </section>
    );
  }

  const signer =
    handlers.find((handler) => handler.handler_id === signedOffBy)?.name ??
    signedOffBy;
  const signOff =
    signedOffBy !== null && claim.signed_off_on !== null
      ? `Signed off by ${signer ?? ""} on ${formatTime(claim.signed_off_on)}.`
      : null;

  if (claim.paid_amount !== null) {
    return (
      <section>
        <p>Paid {formatMoney(claim.paid_amount)}.</p>
        {signOff && <p>{signOff}</p>}
      </section>
    );
  }

  if (signOff) {
    return (
      <section>
        <p>{signOff}</p>
        <p>Payment in progress.</p>
      </section>
    );
  }

  return null;
}
