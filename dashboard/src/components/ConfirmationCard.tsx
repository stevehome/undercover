import { Link } from "react-router";
import { formatMoney } from "../money";
import type { ConfirmationCard as Card, Redress } from "../types";

function Amount({ children }: Readonly<{ children: number }>) {
  return <span className="mono">{formatMoney(children)}</span>;
}

function SignOffDetails({
  card,
}: Readonly<{ card: Extract<Card, { kind: "sign_off" }> }>) {
  return (
    <>
      <dt>It will pay</dt>
      <dd>
        <Amount>{card.payout}</Amount>
      </dd>
      <dt>The agent&apos;s reason</dt>
      <dd>{card.reason}</dd>
    </>
  );
}

function RedressDetails({
  redress,
  reason,
}: Readonly<{ redress: Redress; reason: string | null }>) {
  return (
    <>
      <dt>Owed on the claim</dt>
      <dd>
        <Amount>{redress.claim_amount}</Amount>
      </dd>
      <dt>Compensation</dt>
      <dd>
        <Amount>{redress.compensation}</Amount>
      </dd>
      <dt>Interest</dt>
      <dd>
        <Amount>{redress.interest}</Amount>
      </dd>
      <dt>It will pay</dt>
      <dd>
        <Amount>{redress.total}</Amount>
      </dd>
      {reason !== null && (
        <>
          <dt>The ombudsman&apos;s reason</dt>
          <dd>{reason}</dd>
        </>
      )}
    </>
  );
}

/** The Copilot's question before it pays: what will be paid, to whose claim, and why.
 * Nothing is paid until the handler signs off. */
export function ConfirmationCard({
  card,
  onAnswer,
}: Readonly<{ card: Card; onAnswer: (confirmed: boolean) => void }>) {
  const signOff = card.kind === "sign_off";
  return (
    <section
      className="confirmation-card"
      aria-label={signOff ? "Confirm the sign-off" : "Confirm the redress"}
    >
      <h3>{signOff ? "Sign off this payout?" : "Pay this redress?"}</h3>
      <dl>
        <dt>Claim</dt>
        <dd>
          <Link to={`/claims/${card.claim_id}`} className="mono">
            {card.claim_id}
          </Link>
        </dd>
        <dt>Customer</dt>
        <dd>{card.customer.name}</dd>
        {card.kind === "sign_off" ? (
          <SignOffDetails card={card} />
        ) : (
          <RedressDetails redress={card.redress} reason={card.reason} />
        )}
      </dl>
      <div className="actions">
        <button
          type="button"
          className="secondary"
          onClick={() => {
            onAnswer(false);
          }}
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={() => {
            onAnswer(true);
          }}
        >
          {signOff ? "Sign off and pay" : "Pay redress"}
        </button>
      </div>
    </section>
  );
}
