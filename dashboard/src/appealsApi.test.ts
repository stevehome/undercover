import { afterEach, expect, it, vi } from "vitest";
import { appeal, appealToWire, upheld } from "./appealFixtures";
import {
  fetchAppealFigures,
  fetchAppeals,
  fetchClaimAppeal,
  payRedress,
  recordAppeal,
  recordAppealOutcome,
} from "./appealsApi";
import { requestUrl } from "./testHelpers";
import type { FetchInput } from "./testHelpers";

vi.mock("./auth", () => import("./testAuth"));

afterEach(() => {
  vi.unstubAllGlobals();
});

function serve(body: unknown, status = 200) {
  const calls: { url: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: FetchInput, init?: RequestInit) => {
      calls.push({
        url: requestUrl(input),
        body:
          typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    }),
  );
  return calls;
}

it("reads the appeals with their amounts in cents", async () => {
  serve([appealToWire(upheld())]);

  const [read] = await fetchAppeals();

  expect(read.redress?.total).toBe(21710);
  expect(read.claim.payout).toBe(37600);
  expect(read.status).toBe("upheld");
});

it("reads a claim's appeal, or null when it has none", async () => {
  serve(null);
  expect(await fetchClaimAppeal("CLM-1001")).toBeNull();

  serve(appealToWire(appeal()));
  expect((await fetchClaimAppeal("CLM-1601"))?.label).toBe("appeal open");
});

it("reads a payment's amount in cents", async () => {
  const paid = upheld({
    label: "appeal upheld, redress paid",
    redress_payment: {
      amount: 21710,
      signed_off_by: "Dana Whitfield",
      paid_on: "2026-11-16T11:00:00+00:00",
    },
  });
  serve(appealToWire(paid));

  expect((await fetchClaimAppeal("CLM-1601"))?.redress_payment?.amount).toBe(
    21710,
  );
});

it("refuses an appeal of a status it doesn't know", async () => {
  serve([{ ...appealToWire(appeal()), status: "withdrawn" }]);

  await expect(fetchAppeals()).rejects.toThrow("appeal status");
});

it("reads the figures with the share as a number and the redress in cents", async () => {
  serve({
    open: 2,
    upheld: 3,
    not_upheld: 3,
    upheld_share: "0.5000",
    redress_paid: "217.10",
    redress_waiting: "901.50",
  });

  expect(await fetchAppealFigures()).toEqual({
    open: 2,
    upheld: 3,
    not_upheld: 3,
    upheld_share: 0.5,
    redress_paid: 21710,
    redress_waiting: 90150,
  });
});

it("reads no share while nothing is decided", async () => {
  serve({
    open: 1,
    upheld: 0,
    not_upheld: 0,
    upheld_share: null,
    redress_paid: "0.00",
    redress_waiting: "0.00",
  });

  expect((await fetchAppealFigures()).upheld_share).toBeNull();
});

it("sends an appeal and an outcome to their routes, the amounts as dollars", async () => {
  const calls = serve({});

  await recordAppeal("CLM-1001", {
    ombudsman_reference: "OMB-1",
    received_on: "2026-11-20",
    grounds: "Late.",
  });
  await recordAppealOutcome("CLM-1001", {
    outcome: "upheld",
    decided_on: "2026-11-25",
    reason: "Unclear.",
    claim_amount: 12000,
    compensation: 5000,
    interest: 150,
  });
  await payRedress("CLM-1001");

  expect(calls.map((c) => c.url)).toEqual([
    "/api/claims/CLM-1001/appeal",
    "/api/claims/CLM-1001/appeal/outcome",
    "/api/claims/CLM-1001/appeal/redress",
  ]);
  expect(calls[1].body).toMatchObject({
    claim_amount: "120.00",
    compensation: "50.00",
    interest: "1.50",
  });
});

it("says what the backend gave as the reason for a refusal", async () => {
  serve({ detail: "This claim already has an appeal" }, 409);

  await expect(payRedress("CLM-1001")).rejects.toThrow(
    "This claim already has an appeal",
  );
});
