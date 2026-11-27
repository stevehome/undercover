import { useState } from "react";
import { payRedress } from "../appealsApi";
import { formatMoney } from "../money";
import type { Redress } from "../types";
import { useMe } from "../useMe";
import { ConfirmDialog } from "./ConfirmDialog";

/** Pay an upheld appeal's redress, after the handler confirms; only a handler who can
 * sign off a payout over the limit sees the button. */
export function PayRedress({
  claimId,
  redress,
  onPaid,
}: Readonly<{ claimId: string; redress: Redress; onPaid: () => void }>) {
  const me = useMe();
  const [asking, setAsking] = useState(false);
  const [message, setMessage] = useState("");

  if (!me?.can_approve_over_limit) {
    return (
      <p>
        {me?.name ?? "You"} can&apos;t pay this redress: only a handler who can
        sign off payouts over the limit can.
      </p>
    );
  }

  const pay = () => {
    setAsking(false);
    setMessage("");
    payRedress(claimId)
      .then(onPaid)
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "Could not pay.");
      });
  };

  return (
    <div>
      {message && <p role="alert">{message}</p>}
      <button
        type="button"
        onClick={() => {
          setAsking(true);
        }}
      >
        Pay redress as {me.name}
      </button>
      {asking && (
        <ConfirmDialog
          title={`Pay the redress on ${claimId}?`}
          confirmLabel="Pay redress"
          onConfirm={pay}
          onCancel={() => {
            setAsking(false);
          }}
        >
          <p>
            This pays <span className="mono">{formatMoney(redress.total)}</span>
            , once, and your name goes on the payment.
          </p>
        </ConfirmDialog>
      )}
    </div>
  );
}
