import { expect, it } from "vitest";
import {
  formatCost,
  formatMoney,
  parseCents,
  parseNanos,
  toWireAmount,
} from "./money";

it.each([
  ["0.00", 0],
  ["0.07", 7],
  ["1234.50", 123450],
  ["19.99", 1999],
])("reads %s as %i cents and writes it back", (wire, cents) => {
  expect(parseCents(wire)).toBe(cents);
  expect(toWireAmount(cents)).toBe(wire);
});

it("formats cents for people with separators", () => {
  expect(formatMoney(123450)).toBe("$1,234.50");
  expect(formatMoney(5)).toBe("$0.05");
});

it("reads a wire model cost as billionths of a dollar and formats it", () => {
  expect(parseNanos("0.000138675")).toBe(138675);
  expect(parseNanos("0.00312")).toBe(3120000);
  expect(parseNanos("1.5")).toBe(1500000000);
  expect(formatCost(3120000)).toBe("$0.0031");
  expect(formatCost(0)).toBe("$0.0000");
  expect(formatCost(1500000000)).toBe("$1.5000");
});
