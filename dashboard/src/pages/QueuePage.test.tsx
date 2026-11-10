import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { summaryToWire } from "../testHelpers";
import type { ClaimSummary } from "../types";
import { QueuePage } from "./QueuePage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

const claims: ClaimSummary[] = [
  {
    claim_id: "CLM-1001",
    claim_type: "trip_delay",
    summary: "Flight home canceled",
    amount_claimed: 42000,
    status: "waiting",
  },
  {
    claim_id: "CLM-1002",
    claim_type: "baggage",
    summary: "Lost bag",
    amount_claimed: 30000,
    status: "decided",
  },
];

function stubFetch() {
  const impl = (): Promise<Response> =>
    Promise.resolve(new Response(JSON.stringify(claims.map(summaryToWire))));
  vi.stubGlobal("fetch", vi.fn(impl));
}

it("shows dashes in the totals until the data arrives", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>(() => undefined)),
  );

  render(
    <MemoryRouter>
      <QueuePage />
    </MemoryRouter>,
  );

  expect(screen.getByText("Waiting").nextElementSibling?.textContent).toBe("–");
});

it("lists claims with their status", async () => {
  stubFetch();

  render(
    <MemoryRouter>
      <QueuePage />
    </MemoryRouter>,
  );

  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText("CLM-1002")).toBeDefined();
  expect(screen.getByText("waiting")).toBeDefined();
  expect(screen.getByText("Waiting").nextElementSibling?.textContent).toBe("1");
  expect(screen.getByText("Decided").nextElementSibling?.textContent).toBe("1");
  expect(screen.getByText("decided")).toBeDefined();
});

it("says so when the queue cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response("down", { status: 500 }))),
  );

  render(
    <MemoryRouter>
      <QueuePage />
    </MemoryRouter>,
  );

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Could not load the latest.",
  );
});
