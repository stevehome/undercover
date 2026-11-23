import type { APIRequestContext } from "@playwright/test";
import { agentHeaders } from "./agentKey";
import { handlerHeaders } from "./signIn";

export interface StartedRun {
  run_id: number;
  claims: { claim_id: string }[];
}

async function readRun(request: APIRequestContext, runId: number) {
  const response = await request.get(`/api/runs/${String(runId)}`, {
    headers: agentHeaders,
  });
  return (await response.json()) as StartedRun;
}

/** Start a dispatch as Dana does, which the app creates and the stand-in agent takes. */
export async function startDispatch(
  request: APIRequestContext,
  concurrency: number,
) {
  const started = await request.post("/api/dispatches", {
    headers: await handlerHeaders(request),
    data: { concurrency },
  });
  return readRun(
    request,
    ((await started.json()) as { run_id: number }).run_id,
  );
}

/** Start an evaluation as Dana does. */
export async function startEvaluation(
  request: APIRequestContext,
  evalSet: "evaluation" | "held_out",
  tiny: boolean,
) {
  const started = await request.post("/api/evaluations", {
    headers: await handlerHeaders(request),
    data: { concurrency: 5, eval_set: evalSet, tiny },
  });
  return readRun(
    request,
    ((await started.json()) as { run_id: number }).run_id,
  );
}

/** Start a round as Dana does, and find the stretch of work that holds it. */
export async function startRound(request: APIRequestContext) {
  const started = await request.post("/api/rounds", {
    headers: await handlerHeaders(request),
  });
  const { round_id: roundId } = (await started.json()) as { round_id: number };
  const stretch = await request.get(
    `/api/improver/rounds/${String(roundId)}/stretch`,
    { headers: agentHeaders },
  );
  const { run_id: runId } = (await stretch.json()) as { run_id: number };
  return { roundId, runId };
}

/** Stop whatever the last test left running, so the next one is not refused. */
export async function endWork(request: APIRequestContext) {
  const current = await request.get("/api/runs/current", {
    headers: await handlerHeaders(request),
  });
  const run = (await current.json()) as {
    run_id: number;
    status: string;
  } | null;
  if (run?.status === "running") {
    await request.post(`/api/runs/${String(run.run_id)}/stop`, {
      headers: agentHeaders,
      data: { reason: "The test ended" },
    });
  }
}

const standIn = "http://127.0.0.1:8003";

/** What the stand-in agent was asked for under one operation, in order. */
export async function askedFor(
  request: APIRequestContext,
  operation: string,
): Promise<Record<string, unknown>[]> {
  const calls = (await (
    await request.get(`${standIn}/calls`)
  ).json()) as string[];
  const bodies = (await (
    await request.get(`${standIn}/bodies`)
  ).json()) as Record<string, unknown>[];
  return bodies.filter((_, index) => calls[index] === operation);
}

/** The app's latest run: what it created when a handler pressed start. */
export async function currentRun(request: APIRequestContext) {
  const response = await request.get("/api/runs/current", {
    headers: await handlerHeaders(request),
  });
  return (await response.json()) as {
    run_id: number;
    kind: string;
    status: string;
    concurrency: number;
    eval_set: string | null;
    tiny: boolean | null;
  } | null;
}
