import { useCallback, useState } from "react";
import { useParams } from "react-router";
import { fetchClaim, fetchSteps, runAgent } from "../api";
import { fetchClaimAppeal } from "../appealsApi";
import { AppealPanel } from "../components/AppealPanel";
import { ContextUsed } from "../components/ContextUsed";
import { DecisionPanel } from "../components/DecisionPanel";
import { LoadError } from "../components/LoadError";
import { Loading } from "../components/Loading";
import { PageHeader } from "../components/PageHeader";
import { PaymentPanel } from "../components/PaymentPanel";
import { StatusPill } from "../components/StatusPill";
import { StepList } from "../components/StepList";
import { formatMoney } from "../money";
import type { Appeal, Claim, Step } from "../types";
import { usePolling } from "../usePolling";

export function ClaimPage() {
  const { claimId } = useParams<{ claimId: string }>();
  const [claim, setClaim] = useState<Claim | null>(null);
  const [steps, setSteps] = useState<Step[]>([]);
  const [appeal, setAppeal] = useState<Appeal | null>(null);

  const load = useCallback(
    () =>
      Promise.all([
        fetchClaim(claimId ?? "").then(setClaim),
        fetchSteps(claimId ?? "").then(setSteps),
        fetchClaimAppeal(claimId ?? "").then(setAppeal),
      ]),
    [claimId],
  );
  const failed = usePolling(load, claim?.status !== "decided");

  if (!claim) {
    return (
      <main className="panel">{failed ? <LoadError /> : <Loading />}</main>
    );
  }

  return (
    <main className="panel">
      <PageHeader
        title={
          <>
            <span className="mono">{claim.claim_id}</span>{" "}
            <StatusPill status={claim.status} />
            {appeal && (
              <>
                {" "}
                <StatusPill status={appeal.label} />
              </>
            )}
          </>
        }
      >
        {claim.summary}
      </PageHeader>
      {failed && <LoadError />}

      {claim.status === "waiting" && (
        <button
          onClick={() => {
            void runAgent(claim.claim_id).then(() =>
              fetchClaim(claim.claim_id).then(setClaim),
            );
          }}
          type="button"
        >
          Run agent
        </button>
      )}

      <StepList steps={steps} />
      <ContextUsed steps={steps} />

      <h2>The story</h2>
      <p>{claim.story}</p>

      <h2>Items claimed</h2>
      <ul>
        {claim.items.map((item) => (
          <li key={item.description}>
            {item.description}:{" "}
            <span className="mono">{formatMoney(item.amount)}</span>
          </li>
        ))}
      </ul>

      <h2>The policy</h2>
      <p>
        {claim.policy.plan} plan, trip to {claim.policy.trip.destination} (
        {claim.policy.trip.departs_on} to {claim.policy.trip.returns_on})
      </p>

      <h2>The customer's previous claims</h2>
      {claim.customer_previous_claims.length === 0 ? (
        <p>None.</p>
      ) : (
        <ul>
          {claim.customer_previous_claims.map((previous) => (
            <li key={previous.claim_id}>
              {previous.summary} — {previous.outcome}
            </li>
          ))}
        </ul>
      )}

      <DecisionPanel claim={claim} />

      <PaymentPanel
        claim={claim}
        onUpdated={() => {
          void fetchClaim(claim.claim_id).then(setClaim);
        }}
      />

      <AppealPanel
        claim={claim}
        appeal={appeal}
        onChanged={() => {
          void fetchClaimAppeal(claim.claim_id).then(setAppeal);
        }}
      />
    </main>
  );
}
