import { Link } from "react-router";
import { formatMoney } from "../money";
import type { ConfirmationCard as Card } from "../types";

/** The Copilot's question before it pays: what will be paid, to whose claim, and why
 * the agent approved it. Nothing is paid until the handler signs off. */
export function ConfirmationCard({
  card,
  onAnswer,
}: Readonly<{ card: Card; onAnswer: (confirmed: boolean) => void }>) {
  return (
    <section className="confirmation-card" aria-label="Confirm the sign-off">
      <h3>Sign off this payout?</h3>
      <dl>
        <dt>Claim</dt>
        <dd>
          <Link to={`/claims/${card.claim_id}`} className="mono">
            {card.claim_id}
          </Link>
        </dd>
        <dt>Customer</dt>
        <dd>{card.customer.name}</dd>
        <dt>It will pay</dt>
        <dd className="mono">{formatMoney(card.payout)}</dd>
        <dt>The agent&apos;s reason</dt>
        <dd>{card.reason}</dd>
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
          Sign off and pay
        </button>
      </div>
    </section>
  );
}
