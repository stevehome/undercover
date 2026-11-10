import { expect, it } from "vitest";
import { describeAnswer, formatShare } from "./measures";

it("formats a share as a percentage", () => {
  expect(formatShare(0.96)).toBe("96.0%");
});

it("describes an answer with its payout only for an approval", () => {
  expect(describeAnswer("approve", 42000)).toBe("approve, $420.00");
  expect(describeAnswer("refer", 0)).toBe("refer");
  expect(describeAnswer(null, null)).toBe("no decision");
});
