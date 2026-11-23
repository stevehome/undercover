import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it } from "vitest";
import type { Run } from "../types";
import { RunPanel } from "./RunPanel";

afterEach(cleanup);

function run(overrides: Partial<Run>): Run {
  return {
    run_id: 3,
    kind: "dispatch",
    status: "running",
    concurrency: 3,
    model: "openai/gpt-6-luna",
    reasoning_effort: "low",
    started_on: "2026-06-03T09:00:00+00:00",
    finished_on: null,
    stopped_reason: null,
    claims: [],
    model_calls: 0,
    total_tokens: 0,
    cost_nanos: 0,
    work_ms: 0,
    summary: {
      approved: 0,
      declined: 0,
      referred: 0,
      waiting_for_sign_off: [],
      left_for_a_handler: [],
      still_in_progress: [],
    },
    ...overrides,
  };
}

const show = (value: Run) =>
  render(
    <MemoryRouter>
      <RunPanel run={value} />
    </MemoryRouter>,
  );

it("says why a stopped run stopped", () => {
  show(
    run({ status: "stopped", stopped_reason: "The agent stopped answering" }),
  );

  expect(
    screen.getByText("Stopped: The agent stopped answering."),
  ).toBeDefined();
});

it("says nothing of stopping for a run that is going", () => {
  show(run({}));

  expect(screen.queryByText(/^Stopped:/)).toBeNull();
});
