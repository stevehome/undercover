import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "../types";
import { DecisionPanel } from "./DecisionPanel";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function claim(overrides: Partial<Claim>): Claim {
  return {
    decision: "approve",
    payout: 95000,
    reason: "A covered trip delay with receipts.",
    policy_reference: "Section 3",
    decided_on: "2026-06-02T09:30:00+00:00",
    decided_by: "UnderCover Agent, configuration version 1",
    manual_version: "2026.2",
    calculation: [
      { step: "Hotel", amount: 100000 },
      { step: "Less the deductible", amount: -5000 },
    ],
    sent_back_decisions: [],
    ...overrides,
  } as Claim;
}

it("shows nothing until a decision is recorded", () => {
  render(<DecisionPanel claim={claim({ decision: null })} />);

  expect(screen.queryByText("The decision")).toBeNull();
});

it("shows the decision, its payout, reason and section", () => {
  render(<DecisionPanel claim={claim({})} />);

  expect(screen.getByText("approve, $950.00")).toBeDefined();
  expect(screen.getByText("A covered trip delay with receipts.")).toBeDefined();
  expect(screen.getByText("Section 3")).toBeDefined();
});

it("shows who made the decision and the manual's version", () => {
  render(<DecisionPanel claim={claim({})} />);

  expect(
    screen.getByText("UnderCover Agent, configuration version 1"),
  ).toBeDefined();
  expect(screen.getByText("Version 2026.2")).toBeDefined();
  expect(screen.getByText("Decided")).toBeDefined();
});

it("shows the calculation line by line, a deduction with its sign", () => {
  render(<DecisionPanel claim={claim({})} />);

  expect(screen.getByText("How the payout was worked out")).toBeDefined();
  const rows = screen.getAllByRole("row");
  expect(within(rows[1]).getByText("$1,000.00")).toBeDefined();
  expect(within(rows[2]).getByText("Less the deductible")).toBeDefined();
  expect(within(rows[2]).getByText("-$50.00")).toBeDefined();
});

it("shows no calculation for a referral", () => {
  render(
    <DecisionPanel
      claim={claim({
        decision: "refer",
        payout: 0,
        calculation: null,
        decided_by: "Security check",
      })}
    />,
  );

  expect(screen.getByText("refer")).toBeDefined();
  expect(screen.getByText("Security check", { selector: "dd" })).toBeDefined();
  expect(screen.queryByText("How the payout was worked out")).toBeNull();
});

const sentBack = {
  decision: "approve" as const,
  payout: 120000,
  reason: "A covered claim.",
  policy_reference: "Section 7",
  decided_by: "UnderCover Agent, configuration version 1",
  decided_on: "2026-06-02T09:00:00+00:00",
  calculation: [{ step: "Hospital bill", amount: 120000 }],
  manual_version: "2026.2",
  note: "The receipts don't match the dates.",
  sent_back_by: "HND-01",
  sent_back_on: "2026-06-02T10:00:00+00:00",
};

it("shows each decision that was sent back with its note, beside the current one", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify([{ handler_id: "HND-01", name: "Dana Whitfield" }]),
        ),
      ),
  );

  render(<DecisionPanel claim={claim({ sent_back_decisions: [sentBack] })} />);

  expect(screen.getByText("A decision sent back")).toBeDefined();
  expect(screen.getByText("approve, $1,200.00")).toBeDefined();
  expect(
    await screen.findByText(/Sent back by Dana Whitfield on .*: The receipts/),
  ).toBeDefined();
  expect(screen.getByText("The decision")).toBeDefined();
  expect(screen.getByText("approve, $950.00")).toBeDefined();
});

it("says when a claim is waiting for the agent's next dispatch", () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]")));

  render(
    <DecisionPanel
      claim={claim({
        status: "sent back",
        decision: null,
        sent_back_decisions: [sentBack],
      })}
    />,
  );

  expect(
    screen.getByText(/decide it again at the next dispatch/),
  ).toBeDefined();
});
