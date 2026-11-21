import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { Claim } from "../types";
import { DecisionPanel } from "./DecisionPanel";

afterEach(cleanup);

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
