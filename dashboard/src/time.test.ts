import { expect, it } from "vitest";
import { formatDuration, formatTime } from "./time";

it("formats a timestamp with its date and time", () => {
  const text = formatTime("2026-06-03T14:30:00+00:00");

  expect(text).toContain("2026");
  expect(text).toMatch(/\d{1,2}:\d{2}/);
});

it("formats a working time in seconds, or minutes and seconds", () => {
  expect(formatDuration(27900)).toBe("27.9 s");
  expect(formatDuration(123000)).toBe("2 min 3 s");
});
