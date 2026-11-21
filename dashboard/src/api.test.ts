import { afterEach, expect, it, vi } from "vitest";
import { fetchClaim, fetchClaims, fetchSteps, startDispatch } from "./api";
import { accessToken, signOut } from "./testAuth";

vi.mock("./auth", () => import("./testAuth"));

afterEach(() => {
  vi.unstubAllGlobals();
});

it("rejects instead of returning an error body as data", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(new Response('{"detail":"No claim"}', { status: 404 })),
    ),
  );

  await expect(fetchClaim("CLM-9999")).rejects.toThrow("404");
});

it("reads wire amounts as whole cents", async () => {
  const summary = { claim_id: "CLM-1001", amount_claimed: "1234.50" };
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify([summary])))),
  );

  const [claim] = await fetchClaims();

  expect(claim.amount_claimed).toBe(123450);
});

it("reads each kind of step with its own details", async () => {
  const source = { system: "Claims operations", owner: "Head", reviewed: "x" };
  const wire = [
    { recorded_on: "1", kind: "note", text: "Read", details: {} },
    {
      recorded_on: "2",
      kind: "tool_call",
      text: "Called a",
      details: { tool: "a" },
    },
    {
      recorded_on: "3",
      kind: "lookup",
      text: "Looked",
      details: { files: { "f.md": source } },
    },
    {
      recorded_on: "4",
      kind: "memory_search",
      text: "Searched",
      details: { found: ["m"] },
    },
    {
      recorded_on: "5",
      kind: "memory_save",
      text: "Saved",
      details: { saved: ["s"] },
    },
    {
      recorded_on: "6",
      kind: "refusal",
      text: "Refused",
      details: { source: "the app", detail: "No" },
    },
  ];
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(wire)))),
  );

  const steps = await fetchSteps("CLM-1001");

  expect(steps.map((step) => step.kind)).toEqual(wire.map((step) => step.kind));
  expect(steps[2]).toMatchObject({ kind: "lookup", files: { "f.md": source } });
  expect(steps[5]).toMatchObject({ source: "the app", detail: "No" });
});

it("refuses a step of a kind it doesn't know", async () => {
  const wire = [{ recorded_on: "1", kind: "gossip", text: "x", details: {} }];
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(wire)))),
  );

  await expect(fetchSteps("CLM-1001")).rejects.toThrow("unknown kind: gossip");
});

it("reads a claim's calculation as cents, a deduction with its sign", async () => {
  const claim = {
    claim_id: "CLM-1001",
    amount_claimed: "1000.00",
    items: [],
    payout: "950.00",
    paid_amount: null,
    calculation: [
      { step: "Hotel", amount: "1000.00" },
      { step: "Less the deductible", amount: "-50.00" },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(claim)))),
  );

  const read = await fetchClaim("CLM-1001");

  expect(read.calculation?.map((line) => line.amount)).toEqual([100000, -5000]);
});

it("sends the signed-in handler's token with an action", async () => {
  const fetchMock = vi.fn(() =>
    Promise.resolve(new Response('{"run_id":1}', { status: 202 })),
  );
  vi.stubGlobal("fetch", fetchMock);

  await startDispatch(3);

  const [, init] = (
    fetchMock.mock.calls as unknown as [string, RequestInit][]
  )[0];
  expect(new Headers(init.headers).get("Authorization")).toBe(
    "Bearer test-token",
  );
});

it("sends no token when nobody is signed in", async () => {
  accessToken.mockResolvedValueOnce(null as unknown as string);
  const fetchMock = vi.fn(() => Promise.resolve(new Response("[]")));
  vi.stubGlobal("fetch", fetchMock);

  await fetchClaims();

  const [, init] = (
    fetchMock.mock.calls as unknown as [string, RequestInit][]
  )[0];
  expect(new Headers(init.headers).has("Authorization")).toBe(false);
});

it("signs the handler out when the backend refuses their token", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(new Response('{"detail":"Sign in"}', { status: 401 })),
    ),
  );

  await expect(startDispatch(3)).rejects.toThrow("Sign in");

  expect(signOut).toHaveBeenCalled();
});
