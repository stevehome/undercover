import { accessToken, signOut } from "./auth";
import { parseCents, parseNanos } from "./money";
import type {
  Claim,
  ClaimGrade,
  ClaimSummary,
  EvalSet,
  Evaluation,
  EvaluationClaim,
  Handler,
  Item,
  Run,
  RunSummary,
  Setting,
  Step,
  AllowedModel,
  Configuration,
  ConfigurationDiff,
  DiffLine,
  Recipe,
  Round,
  Scores,
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

/** Call the backend with the signed-in handler's token; a 401 signs them out. */
async function send(path: string, init: RequestInit = {}): Promise<Response> {
  const token = await accessToken();
  const headers = new Headers(init.headers);
  if (token !== null) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) await signOut();
  return response;
}

async function getJson<T>(path: string): Promise<T> {
  const response = await send(path);
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
  const response = await send(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body && JSON.stringify(body),
  });
  if (!response.ok) throw await refusal(path, response);
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

type WireScores = Omit<
  Scores,
  "accuracy" | "grade" | "cost_per_claim_nanos" | "seconds_per_claim"
> & {
  accuracy: string | null;
  grade: string | null;
  cost_per_claim: string | null;
  seconds_per_claim: string | null;
};

const optionalNumber = (value: string | null) =>
  value === null ? null : Number(value);

function scoresFromWire(wire: WireScores): Scores {
  return {
    runs: wire.runs,
    accuracy: optionalNumber(wire.accuracy),
    grade: optionalNumber(wire.grade),
    cost_per_claim_nanos:
      wire.cost_per_claim === null ? null : parseNanos(wire.cost_per_claim),
    seconds_per_claim: optionalNumber(wire.seconds_per_claim),
  };
}

export async function fetchConfigurations(): Promise<Configuration[]> {
  const wire = await getJson<
    (Omit<Configuration, "held_out"> & { held_out: WireScores })[]
  >("/api/configurations");
  return wire.map((version) => ({
    ...version,
    held_out: scoresFromWire(version.held_out),
  }));
}

export const fetchRecipes = () => getJson<Recipe[]>("/api/recipes");

export const fetchRecipeDiff = (version: number) =>
  getJson<{ version: number; from_version: number | null; lines: DiffLine[] }>(
    `/api/recipes/${String(version)}/diff`,
  );

type WireRound = Omit<
  Round,
  "held_out_before" | "held_out_after" | "cost_nanos" | "spending_limit"
> & {
  held_out_before: WireScores | null;
  held_out_after: WireScores | null;
  cost: string;
  spending_limit: string;
};

/** The improvement rounds, newest first, with cost and limit converted. */
export async function fetchRounds(): Promise<Round[]> {
  const wire = await getJson<WireRound[]>("/api/rounds");
  return wire.map(({ cost, spending_limit, ...round }) => ({
    ...round,
    held_out_before:
      round.held_out_before && scoresFromWire(round.held_out_before),
    held_out_after:
      round.held_out_after && scoresFromWire(round.held_out_after),
    cost_nanos: parseNanos(cost),
    spending_limit: parseCents(spending_limit),
  }));
}

export const startRound = () => post("/api/rounds");

export const stopRound = (roundId: number) =>
  post(`/api/rounds/${String(roundId)}/stop`);

export const decideProposal = (
  proposalId: number,
  decision: "approve" | "reject",
  reason: string,
) =>
  post(`/api/proposals/${String(proposalId)}/decision`, { decision, reason });

export const fetchConfigurationDiff = (version: number) =>
  getJson<ConfigurationDiff>(`/api/configurations/${String(version)}/diff`);

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

type WireGrade = Omit<ClaimGrade, "score" | "same_grounds" | "same_section"> & {
  score: string;
  same_grounds: string;
  same_section: string;
};

type WireEvaluation = Omit<Evaluation, "measures" | "claims"> & {
  measures: {
    decision_accuracy: string;
    accuracy: string;
    straight_through: string;
    cost_of_mistakes: string;
    model_cost_per_claim: string;
    seconds_per_claim: string;
    run_seconds: string | null;
    grade: string | null;
    judge_cost: string;
  };
  claims: (Omit<
    EvaluationClaim,
    | "handler_payout"
    | "agent_payout"
    | "mistake_cost"
    | "cost_nanos"
    | "grade"
    | "judge_cost_nanos"
  > & {
    handler_payout: string;
    agent_payout: string | null;
    mistake_cost: string;
    cost: string;
    grade: WireGrade | null;
    judge_cost: string;
  })[];
};

function evaluationFromWire(wire: WireEvaluation): Evaluation {
  const { measures, claims, ...rest } = wire;
  return {
    ...rest,
    measures: {
      decision_accuracy: Number(measures.decision_accuracy),
      accuracy: Number(measures.accuracy),
      straight_through: Number(measures.straight_through),
      cost_of_mistakes: parseCents(measures.cost_of_mistakes),
      model_cost_per_claim_nanos: parseNanos(measures.model_cost_per_claim),
      seconds_per_claim: Number(measures.seconds_per_claim),
      run_seconds:
        measures.run_seconds === null ? null : Number(measures.run_seconds),
      grade: measures.grade === null ? null : Number(measures.grade),
      judge_cost_nanos: parseNanos(measures.judge_cost),
    },
    claims: claims.map(({ cost, judge_cost, grade, ...claim }) => ({
      ...claim,
      grade:
        grade === null
          ? null
          : {
              ...grade,
              score: Number(grade.score),
              same_grounds: Number(grade.same_grounds),
              same_section: Number(grade.same_section),
            },
      judge_cost_nanos: parseNanos(judge_cost),
      handler_payout: parseCents(claim.handler_payout),
      agent_payout: optionalCents(claim.agent_payout),
      mistake_cost: parseCents(claim.mistake_cost),
      cost_nanos: parseNanos(cost),
    })),
  };
}

/** The evaluations, newest first. */
export async function fetchEvaluations(): Promise<Evaluation[]> {
  const wire = await getJson<WireEvaluation[]>("/api/evaluations");
  return wire.map(evaluationFromWire);
}

export async function fetchEvaluation(runId: string): Promise<Evaluation> {
  return evaluationFromWire(
    await getJson<WireEvaluation>(`/api/evaluations/${runId}`),
  );
}

/** Start an evaluation on a labelled set, whole or just its tiny claims. */
export const startEvaluation = (
  concurrency: number,
  evalSet: EvalSet,
  tiny: boolean,
) => post("/api/evaluations", { concurrency, eval_set: evalSet, tiny });

/** Start a dispatch with this many claim agents at once. */
export const startDispatch = (concurrency: number) =>
  post("/api/dispatches", { concurrency });

export const runAgent = (claimId: string) => post(`/api/claims/${claimId}/run`);

export const signOffClaim = (claimId: string) =>
  post(`/api/claims/${claimId}/sign-off`);

/** The signed-in handler, and whether they can sign off over the limit. */
export const fetchMe = () => getJson<Handler>("/api/me");

/** The platform's settings; a count comes as a number and is kept as text. */
export async function fetchSettings(): Promise<Setting[]> {
  const wire = await getJson<
    (Omit<Setting, "value" | "maximum"> & {
      value: string | number;
      maximum: string | number;
    })[]
  >("/api/settings");
  return wire.map((setting) => ({
    ...setting,
    value: String(setting.value),
    maximum: String(setting.maximum),
  }));
}

export const changeSetting = (key: string, value: string) =>
  post(`/api/settings/${key}`, { value });

export const fetchModels = () => getJson<AllowedModel[]>("/api/models");
