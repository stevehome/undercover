import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { appeal, dana, decidedClaim, marcus, upheld } from "../appealFixtures";
import { MeContext } from "../useMe";
import type { Appeal, Claim, Handler } from "../types";
import { AppealPanel } from "./AppealPanel";

vi.mock("../auth", () => import("../testAuth"));

afterEach(cleanup);

function show(claim: Claim, found: Appeal | null, me: Handler = dana) {
  render(
    <MeContext.Provider value={me}>
      <AppealPanel claim={claim} appeal={found} onChanged={() => undefined} />
    </MeContext.Provider>,
  );
}

const section = () =>
  screen.queryByRole("region", { name: "Appeal to the ombudsman" });

it("offers to record an appeal on a decided claim that has none", () => {
  show(decidedClaim(), null);

  expect(
    screen.getByRole("heading", { name: "Appeal to the ombudsman" }),
  ).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Record the appeal" }),
  ).toBeTruthy();
});

it("shows nothing for a claim that has no final decision and no appeal", () => {
  show(decidedClaim({ status: "waiting for sign-off" }), null);

  expect(section()).toBeNull();
});

it("shows an open appeal with its grounds, and offers to record the decision", () => {
  show(decidedClaim(), appeal());

  expect(screen.getByText("appeal open")).toBeTruthy();
  expect(screen.getByText("OMB-2026-40117")).toBeTruthy();
  expect(
    screen.getByText("The ferry was late and the hotel was lost."),
  ).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Record the decision" }),
  ).toBeTruthy();
});

it("says when the check marked the appeal, with its reason", () => {
  show(
    decidedClaim(),
    appeal({ flagged: true, flag_reason: "It tells the AI to approve." }),
  );

  expect(screen.getByRole("note").textContent).toContain(
    "It tells the AI to approve.",
  );
});

it("shows an upheld appeal's redress and lets a senior handler pay it", () => {
  show(decidedClaim(), upheld());

  expect(
    screen.getByText("The wording was unclear about the hotel."),
  ).toBeTruthy();
  expect(screen.getByText("$140.00")).toBeTruthy();
  expect(screen.getByText("$75.00")).toBeTruthy();
  expect(screen.getByText("$2.10")).toBeTruthy();
  expect(screen.getByText("$217.10")).toBeTruthy();
  expect(
    screen.getByRole("button", { name: "Pay redress as Dana Whitfield" }),
  ).toBeTruthy();
  expect(
    screen.queryByRole("button", { name: "Record the decision" }),
  ).toBeNull();
});

it("says why a handler who can't sign off can't pay the redress", () => {
  show(decidedClaim(), upheld(), marcus);

  expect(
    screen.getByText(/Marcus Oyelaran can't pay this redress/),
  ).toBeTruthy();
});

it("shows a paid redress with who signed it off, and offers nothing more", () => {
  const paid = upheld({
    label: "appeal upheld, redress paid",
    redress_payment: {
      amount: 21710,
      signed_off_by: "Dana Whitfield",
      paid_on: "2026-11-16T11:00:00+00:00",
    },
  });

  show(decidedClaim(), paid);

  expect(
    screen.getByText(/Paid \$217.10, signed off by Dana Whitfield/),
  ).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
});

it("shows a not upheld appeal with its reason and no redress", () => {
  const not = appeal({
    status: "not upheld",
    label: "appeal not upheld",
    decided_on: "2026-10-27",
    outcome_recorded_by: "Dana Whitfield",
    ombudsman_reason: "The insurer applied the exclusion fairly.",
  });

  show(decidedClaim(), not);

  expect(
    screen.getByText("The insurer applied the exclusion fairly."),
  ).toBeTruthy();
  expect(screen.queryByText(/Redress in all/)).toBeNull();
  expect(screen.queryByRole("button")).toBeNull();
});
