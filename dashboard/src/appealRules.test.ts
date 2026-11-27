import { expect, it } from "vitest";
import { decidedClaim } from "./appealFixtures";
import { hasFinalDecision } from "./appealRules";

it.each([
  ["a declined claim", {}, true],
  [
    "an approved and paid claim",
    { decision: "approve", paid_amount: 100 },
    true,
  ],
  [
    "an approved claim not paid",
    { decision: "approve", paid_amount: null },
    false,
  ],
  ["a referred claim", { decision: "refer" }, false],
  ["a claim waiting for sign-off", { status: "waiting for sign-off" }, false],
  ["a claim sent back", { status: "sent back" }, false],
  ["an evaluation's claim", { evaluation_run_id: 3 }, false],
] as const)("%s: final is %s", (_what, more, final) => {
  expect(hasFinalDecision(decidedClaim(more))).toBe(final);
});
