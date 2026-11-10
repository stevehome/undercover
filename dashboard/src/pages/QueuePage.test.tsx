import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { requestUrl, summaryToWire } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
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

const finishedRun = {
  run_id: 4,
  kind: "dispatch",
  status: "finished",
  concurrency: 3,
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
  started_on: "2026-01-01T00:00:00Z",
  finished_on: "2026-01-01T00:01:00Z",
  claims: [
    { claim_id: "CLM-1001", status: "done", attempts: 1, note: "Declined" },
    {
      claim_id: "CLM-1002",
      status: "still in progress",
      attempts: 1,
      note: "",
    },
  ],
  model_calls: 9,
  total_tokens: 9000,
  cost: "0.003120000",
  work_ms: 27900,
  summary: {
    approved: 0,
    declined: 1,
    referred: 0,
    waiting_for_sign_off: [{ claim_id: "CLM-1003", payout: "1200.00" }],
    left_for_a_handler: ["CLM-1004"],
    still_in_progress: ["CLM-1002"],
  },
};

interface Stub {
  run?: object | null;
  start?: Response;
}

function stubFetch({ run = null, start }: Stub = {}) {
  const posted: { url: string; body: unknown }[] = [];
  const impl = (input: FetchInput, init?: RequestInit): Promise<Response> => {
    const url = requestUrl(input);
    if (init?.method === "POST") {
      posted.push({ url, body: JSON.parse(init.body as string) });
      return Promise.resolve(start ?? new Response('{"run_id":5}'));
    }
    if (url.endsWith("/runs/current")) {
      return Promise.resolve(new Response(JSON.stringify(run)));
    }
    return Promise.resolve(
      new Response(JSON.stringify(claims.map(summaryToWire))),
    );
  };
  vi.stubGlobal("fetch", vi.fn(impl));
  return posted;
}

function renderPage() {
  render(
    <MemoryRouter>
      <QueuePage />
    </MemoryRouter>,
  );
}

it("shows dashes in the totals until the data arrives", () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>(() => undefined)),
  );

  renderPage();

  expect(screen.getByText("Waiting").nextElementSibling?.textContent).toBe("–");
});

it("lists claims with their status and no run before the first", async () => {
  stubFetch();

  renderPage();

  expect(await screen.findByText("CLM-1001")).toBeDefined();
  expect(screen.getByText("CLM-1002")).toBeDefined();
  expect(screen.getByText("waiting")).toBeDefined();
  expect(screen.getByText("Waiting").nextElementSibling?.textContent).toBe("1");
  expect(screen.getByText("Decided").nextElementSibling?.textContent).toBe("1");
  expect(screen.queryByText(/The current dispatch/)).toBeNull();
});

it("shows the run's claims, its cost and time, and its summary", async () => {
  stubFetch({ run: finishedRun });

  renderPage();

  expect(
    await screen.findByText("The current dispatch (finished)"),
  ).toBeDefined();
  expect(
    screen.getByText(/Model cost \$0\.0031, working time 27\.9 s/),
  ).toBeDefined();
  expect(screen.getByText("still in progress")).toBeDefined();
  expect(screen.getByText("1 declined", { exact: false })).toBeDefined();
  expect(
    screen.getByText("CLM-1003: $1,200.00 waiting for sign-off."),
  ).toBeDefined();
  expect(screen.getByText("Left for a handler: CLM-1004.")).toBeDefined();
  expect(screen.getByText("Still in progress: CLM-1002.")).toBeDefined();
});

it("shows no summary while the run is going", async () => {
  stubFetch({ run: { ...finishedRun, status: "running" } });

  renderPage();

  expect(
    await screen.findByText("The current dispatch (running)"),
  ).toBeDefined();
  expect(screen.queryByRole("region", { name: "Summary" })).toBeNull();
});

it("starts a dispatch with 3 claim agents unless another number is chosen", async () => {
  const posted = stubFetch();
  renderPage();
  const input = await screen.findByLabelText("Claim agents at once");
  expect((input as HTMLInputElement).value).toBe("3");

  fireEvent.click(screen.getByRole("button", { name: "Start a dispatch" }));
  await waitFor(() => {
    expect(posted).toHaveLength(1);
  });
  fireEvent.change(input, { target: { value: "25" } });
  fireEvent.click(screen.getByRole("button", { name: "Start a dispatch" }));
  await waitFor(() => {
    expect(posted).toHaveLength(2);
  });

  expect(posted).toEqual([
    { url: "/api/dispatches", body: { concurrency: 3 } },
    { url: "/api/dispatches", body: { concurrency: 25 } },
  ]);
});

it("says why a start was refused", async () => {
  stubFetch({
    start: new Response(
      '{"detail":"A dispatch or evaluation is already running"}',
      { status: 409 },
    ),
  });
  renderPage();

  fireEvent.click(
    await screen.findByRole("button", { name: "Start a dispatch" }),
  );

  expect((await screen.findByRole("alert")).textContent).toBe(
    "A dispatch or evaluation is already running",
  );
});

it("says so when the agent's service is not running", async () => {
  stubFetch({
    start: new Response('{"detail":"The agent\'s service isn\'t running"}', {
      status: 503,
    }),
  });
  renderPage();

  fireEvent.click(
    await screen.findByRole("button", { name: "Start a dispatch" }),
  );

  expect((await screen.findByRole("alert")).textContent).toBe(
    "The agent's service isn't running",
  );
});

it("says so when the queue cannot be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response("down", { status: 500 }))),
  );

  renderPage();

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Could not load the latest.",
  );
});
