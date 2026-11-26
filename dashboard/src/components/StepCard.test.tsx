import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { step } from "../copilotFixtures";
import type { CardKind, StepState } from "../types";
import { StepCard } from "./StepCard";

beforeEach(() => {
  vi.useFakeTimers();
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

const KINDS: CardKind[] = [
  "claims",
  "customers",
  "context",
  "agent work",
  "memory",
  "action",
];

it.each(KINDS)("shows an icon for the %s kind", (kind) => {
  render(<StepCard step={step("done", kind)} />);

  expect(screen.getByRole("img", { name: kind })).toBeDefined();
});

it("shows the tool, its main input and how long it took when done", () => {
  render(<StepCard step={step("done")} />);

  expect(screen.getByText("get_claim")).toBeDefined();
  expect(screen.getByText("claim_id: CLM-1012")).toBeDefined();
  expect(screen.getByText("Done, 1.2 s")).toBeDefined();
});

it("counts the seconds a working step has run", async () => {
  const started = new Date(Date.now() - 2000).toISOString();
  render(
    <StepCard step={step("working", "claims", { started_on: started })} />,
  );

  expect(screen.getByText(/Working, 2.0 s/)).toBeDefined();
  await act(async () => {
    await vi.advanceTimersByTimeAsync(3000);
  });

  expect(screen.getByText(/Working, 5.0 s/)).toBeDefined();
});

it.each<[StepState, string]>([
  ["refused", "A dispatch is already running"],
  ["failed", "ValueError: boom"],
])("shows the reason a step was %s", (state, reason) => {
  render(<StepCard step={step(state, "action", { reason })} />);

  expect(screen.getByText(reason)).toBeDefined();
  expect(screen.getByText(new RegExp(state, "i"))).toBeDefined();
});

it("stands an action out from a lookup", () => {
  const { container, rerender } = render(
    <StepCard step={step("done", "action")} />,
  );
  expect(container.querySelector(".step-card.action")).not.toBeNull();

  rerender(<StepCard step={step("done", "claims")} />);

  expect(container.querySelector(".step-card.action")).toBeNull();
});

it("opens to what was asked, what came back and where a lookup's files came from", () => {
  const files = {
    "plans.yaml": {
      system: "Policy administration",
      owner: "Product",
      reviewed: "2026-09-01",
    },
  };
  render(<StepCard step={step("done", "context", { files })} />);
  expect(screen.queryByText("Came back")).toBeNull();

  fireEvent.click(screen.getByRole("button"));

  expect(screen.getByText("Asked")).toBeDefined();
  expect(screen.getByText("The claim came back")).toBeDefined();
  expect(
    screen.getByText(/Policy administration, owned by Product/),
  ).toBeDefined();
});

it("says so when nothing was asked or came back", () => {
  render(<StepCard step={step("working", "claims", { input: "" })} />);

  fireEvent.click(screen.getByRole("button"));

  expect(screen.getByText("Nothing")).toBeDefined();
  expect(screen.getByText("Nothing yet")).toBeDefined();
});
