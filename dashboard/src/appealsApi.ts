import { getJson, known, optionalCents, post, redressFromWire } from "./api";
import type { WireRedress } from "./api";
import { parseCents, toWireAmount } from "./money";
import type {
  Appeal,
  AppealFigures,
  AppealStatus,
  NewAppeal,
  NewOutcome,
  RedressPayment,
} from "./types";

type WireAppeal = Omit<
  Appeal,
  "status" | "redress" | "redress_payment" | "claim"
> & {
  status: string;
  redress: WireRedress | null;
  redress_payment: (Omit<RedressPayment, "amount"> & { amount: string }) | null;
  claim: Omit<Appeal["claim"], "payout"> & { payout: string | null };
};

const APPEAL_STATUSES: AppealStatus[] = [
  "with the ombudsman",
  "upheld",
  "not upheld",
];

function toAppeal(wire: WireAppeal): Appeal {
  return {
    ...wire,
    status: known("appeal status", wire.status, APPEAL_STATUSES),
    redress: wire.redress && redressFromWire(wire.redress),
    redress_payment: wire.redress_payment && {
      ...wire.redress_payment,
      amount: parseCents(wire.redress_payment.amount),
    },
    claim: { ...wire.claim, payout: optionalCents(wire.claim.payout) },
  };
}

export async function fetchAppeals(): Promise<Appeal[]> {
  return (await getJson<WireAppeal[]>("/api/appeals")).map(toAppeal);
}

/** A claim's appeal, or null when it has none. */
export async function fetchClaimAppeal(
  claimId: string,
): Promise<Appeal | null> {
  const wire = await getJson<WireAppeal | null>(
    `/api/claims/${claimId}/appeal`,
  );
  return wire && toAppeal(wire);
}

export async function fetchAppealFigures(): Promise<AppealFigures> {
  const wire = await getJson<
    Omit<AppealFigures, "upheld_share" | "redress_paid" | "redress_waiting"> & {
      upheld_share: string | null;
      redress_paid: string;
      redress_waiting: string;
    }
  >("/api/appeals/figures");
  return {
    ...wire,
    upheld_share: wire.upheld_share === null ? null : Number(wire.upheld_share),
    redress_paid: parseCents(wire.redress_paid),
    redress_waiting: parseCents(wire.redress_waiting),
  };
}

export const recordAppeal = (claimId: string, appeal: NewAppeal) =>
  post(`/api/claims/${claimId}/appeal`, appeal);

export const recordAppealOutcome = (claimId: string, outcome: NewOutcome) =>
  post(`/api/claims/${claimId}/appeal/outcome`, {
    ...outcome,
    claim_amount: toWireAmount(outcome.claim_amount),
    compensation: toWireAmount(outcome.compensation),
    interest: toWireAmount(outcome.interest),
  });

export const payRedress = (claimId: string) =>
  post(`/api/claims/${claimId}/appeal/redress`);
