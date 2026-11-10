import { parseCents, parseNanos } from "./money";
import type {
  Claim,
  ClaimSummary,
  Handler,
  Item,
  Run,
  RunSummary,
  Step,
} from "./types";

type WireSummary = Omit<ClaimSummary, "amount_claimed"> & {
  amount_claimed: string;
};

type WireClaim = Omit<
  Claim,
  "amount_claimed" | "items" | "payout" | "paid_amount"
> & {
  amount_claimed: string;
  items: (Omit<Item, "amount"> & { amount: string })[];
  payout: string | null;
  paid_amount: string | null;
};

const optionalCents = (amount: string | null) =>
  amount === null ? null : parseCents(amount);

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${String(response.status)}`);
  return (await response.json()) as T;
}

/** An error whose message is the reason the backend gave, if it gave one. */
async function refusal(path: string, response: Response): Promise<Error> {
  const body = (await response.json().catch(() => ({}))) as {
    detail?: unknown;
  };
  return new Error(
    typeof body.detail === "string"
      ? body.detail
      : `${path}: ${String(response.status)}`,
  );
}

async function post(path: string, body?: object): Promise<void> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body && JSON.stringify(body),
  });
  if (!response.ok) throw await refusal(path, response);
}

async function getInstructions(path: string): Promise<string> {
  return (await getJson<{ instructions: string }>(path)).instructions;
}

export async function fetchClaims(): Promise<ClaimSummary[]> {
  const claims = await getJson<WireSummary[]>("/api/claims");
  return claims.map((claim) => ({
    ...claim,
    amount_claimed: parseCents(claim.amount_claimed),
  }));
}

export async function fetchClaim(claimId: string): Promise<Claim> {
  const claim = await getJson<WireClaim>(`/api/claims/${claimId}`);
  return {
    ...claim,
    amount_claimed: parseCents(claim.amount_claimed),
    items: claim.items.map((item) => ({
      ...item,
      amount: parseCents(item.amount),
    })),
    payout: optionalCents(claim.payout),
    paid_amount: optionalCents(claim.paid_amount),
  };
}

export const fetchSteps = (claimId: string) =>
  getJson<Step[]>(`/api/claims/${claimId}/steps`);

export const fetchHandlers = () => getJson<Handler[]>("/api/handlers");

export const fetchClaimInstructions = () =>
  getInstructions("/api/claim-instructions");

type WireRun = Omit<Run, "cost_nanos" | "summary"> & {
  cost: string;
  summary: Omit<RunSummary, "waiting_for_sign_off"> & {
    waiting_for_sign_off: { claim_id: string; payout: string }[];
  };
};

/** The most recent run, or null before the first one. */
export async function fetchCurrentRun(): Promise<Run | null> {
  const run = await getJson<WireRun | null>("/api/runs/current");
  if (run === null) return null;
  const { cost, summary, ...rest } = run;
  return {
    ...rest,
    cost_nanos: parseNanos(cost),
    summary: {
      ...summary,
      waiting_for_sign_off: summary.waiting_for_sign_off.map((claim) => ({
        ...claim,
        payout: parseCents(claim.payout),
      })),
    },
  };
}

/** Start a dispatch with this many claim agents at once. */
export const startDispatch = (concurrency: number) =>
  post("/api/dispatches", { concurrency });

export const runAgent = (claimId: string) => post(`/api/claims/${claimId}/run`);

export const signOffClaim = (claimId: string, handlerId: string) =>
  post(`/api/claims/${claimId}/sign-off`, { handler_id: handlerId });
