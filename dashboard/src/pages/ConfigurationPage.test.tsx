import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { requestUrl } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import type { Configuration } from "../types";
import { ConfigurationPage } from "./ConfigurationPage";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const heldOut = {
  runs: 2,
  accuracy: "0.8000",
  grade: "1.500",
  cost_per_claim: "0.000100000",
  seconds_per_claim: "10.000",
};

const version = (overrides: Partial<Configuration>) => ({
  version: 1,
  instructions: "Decide the claim.",
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
  reason: "The starting version",
  proposed_by: "seed",
  approved_by: null,
  approved_on: null,
  round_id: null,
  verdict: "kept",
  verdict_reason: null,
  created_on: "2026-01-01T00:00:00+00:00",
  held_out: heldOut,
  ...overrides,
});

function show() {
  const impl = (input: FetchInput): Promise<Response> => {
    const url = requestUrl(input);
    if (url === "/api/configurations/2/diff") {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            version: 2,
            from_version: 1,
            lines: [
              { kind: "removed", text: "Decide the claim." },
              { kind: "added", text: "Decide the claim carefully." },
            ],
            model_before: "openai/gpt-6-luna",
            model_after: "google/gemini-3.5-flash-lite",
            reasoning_effort_before: "low",
            reasoning_effort_after: "low",
          }),
        ),
      );
    }
    return Promise.resolve(
      new Response(
        JSON.stringify([
          version({}),
          version({
            version: 2,
            instructions: "Decide the claim carefully.",
            verdict: "rolled back",
            reason: "Cover the repeat claims.",
          }),
        ]),
      ),
    );
  };
  vi.stubGlobal("fetch", vi.fn(impl));
  render(<ConfigurationPage />);
}

it("shows the current version, which is the highest one kept", async () => {
  show();

  expect(await screen.findByText("Current version: 1")).toBeDefined();
  expect(
    screen.getByText("Decide the claim.", { selector: "pre" }),
  ).toBeDefined();
});

it("lists every version with its verdict and held-out scores, newest first", async () => {
  show();

  await screen.findByText("Current version: 1");
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows[0].textContent).toContain("rolled back");
  expect(rows[1].textContent).toContain("kept");
  expect(rows[1].textContent).toContain("80.0%");
  expect(rows[1].textContent).toContain("1.50");
});

it("shows what a version changed from the one before it", async () => {
  show();
  await screen.findByText("Current version: 1");

  fireEvent.click(screen.getAllByRole("button", { name: "Show changes" })[0]);

  await waitFor(() => {
    expect(screen.getByText("Version 2 changed from version 1")).toBeDefined();
  });
  expect(screen.getByText(/to google\/gemini-3.5-flash-lite/)).toBeDefined();
  expect(screen.getByText("Decide the claim carefully.")).toBeDefined();
});
