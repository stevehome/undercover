import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { wireRound } from "../roundFixtures";
import type { Round, Stage } from "../types";
import { RoundProgress } from "./RoundProgress";

afterEach(cleanup);

const at = (stage: Stage, progress = 0) =>
  ({ ...wireRound({ stage, progress }) }) as unknown as Round;

function current() {
  return screen
    .getAllByRole("listitem")
    .find((item) => item.getAttribute("aria-current") === "step");
}

it.each([
  ["first evaluations", 1, "First evaluations, 1 of 3"],
  ["first evaluations", 2, "First evaluations, 2 of 3"],
  ["first evaluations", 3, "First evaluations, 3 of 3"],
  ["improver working", 0, "The improver is working"],
  ["change waiting", 0, "A change is waiting for approval"],
  ["evaluations", 1, "Evaluations, 1 of 3"],
  ["evaluations", 2, "Evaluations, 2 of 3"],
  ["evaluations", 3, "Evaluations, 3 of 3"],
  ["verdict", 0, "Verdict"],
  ["recipe waiting", 0, "A recipe is waiting for approval"],
] as const)("shows %s (%i) as the step it is on", (stage, progress, label) => {
  render(<RoundProgress round={at(stage, progress)} />);

  expect(current()?.textContent).toBe(label);
});

it("marks the steps before the current one as done", () => {
  render(<RoundProgress round={at("evaluations", 1)} />);

  const items = screen.getAllByRole("listitem");
  expect(items[0].className).toContain("step-done");
  expect(items[5].className).toContain("step-to-do");
});

it("marks every step done when the round is finished", () => {
  render(<RoundProgress round={at("finished")} />);

  expect(
    screen
      .getAllByRole("listitem")
      .every((i) => i.className.includes("step-done")),
  ).toBe(true);
});

it("says a round was stopped", () => {
  render(<RoundProgress round={at("stopped")} />);

  expect(screen.getByText("stopped")).toBeDefined();
  expect(current()).toBeUndefined();
});
