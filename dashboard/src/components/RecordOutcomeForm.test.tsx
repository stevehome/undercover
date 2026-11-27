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
import { RecordOutcomeForm } from "./RecordOutcomeForm";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const button = () =>
  screen.getByRole<HTMLButtonElement>("button", {
    name: "Record the decision",
  });

function fillBasics() {
  fireEvent.change(screen.getByLabelText(/date of the decision/), {
    target: { value: "2026-11-25" },
  });
  fireEvent.change(screen.getByLabelText(/ombudsman.s reason/), {
    target: { value: " Unclear. " },
  });
}

function stubFetch() {
  const calls: { url: string; body: unknown }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: FetchInput, init?: RequestInit) => {
      calls.push({
        url: requestUrl(input),
        body: JSON.parse(typeof init?.body === "string" ? init.body : "{}"),
      });
      return Promise.resolve(new Response("{}"));
    }),
  );
  return calls;
}

it("asks for the three amounts only when the appeal is upheld", () => {
  render(<RecordOutcomeForm claimId="CLM-1001" onRecorded={() => undefined} />);
  expect(screen.getAllByLabelText(/in dollars/)).toHaveLength(3);

  fireEvent.change(screen.getByLabelText(/ombudsman.s decision/), {
    target: { value: "not upheld" },
  });

  expect(screen.queryAllByLabelText(/in dollars/)).toHaveLength(0);
});

it("needs amounts that come to more than zero when upheld, and says so", () => {
  render(<RecordOutcomeForm claimId="CLM-1001" onRecorded={() => undefined} />);
  fillBasics();
  expect(button().disabled).toBe(true);
  expect(screen.getByText(/must come to more than zero/)).toBeTruthy();

  fireEvent.change(screen.getByLabelText(/Interest/), {
    target: { value: "x" },
  });
  expect(button().disabled).toBe(true);

  fireEvent.change(screen.getByLabelText(/Interest/), {
    target: { value: "1.50" },
  });
  expect(button().disabled).toBe(false);
});

it("records an upheld outcome with its amounts in cents", async () => {
  const calls = stubFetch();
  const recorded = vi.fn();
  render(<RecordOutcomeForm claimId="CLM-1001" onRecorded={recorded} />);
  fillBasics();
  fireEvent.change(screen.getByLabelText(/part of the claim still owed/), {
    target: { value: "120" },
  });
  fireEvent.change(screen.getByLabelText(/Compensation/), {
    target: { value: "50.5" },
  });

  fireEvent.click(button());

  await waitFor(() => {
    expect(recorded).toHaveBeenCalled();
  });
  expect(calls[0]).toEqual({
    url: "/api/claims/CLM-1001/appeal/outcome",
    body: {
      outcome: "upheld",
      decided_on: "2026-11-25",
      reason: "Unclear.",
      claim_amount: "120.00",
      compensation: "50.50",
      interest: "0.00",
    },
  });
});

it("records a not upheld outcome with no redress", async () => {
  const calls = stubFetch();
  render(<RecordOutcomeForm claimId="CLM-1001" onRecorded={() => undefined} />);
  fireEvent.change(screen.getByLabelText(/ombudsman.s decision/), {
    target: { value: "not upheld" },
  });
  fillBasics();

  fireEvent.click(button());

  await waitFor(() => {
    expect(calls).toHaveLength(1);
  });
  expect(calls[0].body).toMatchObject({
    outcome: "not upheld",
    claim_amount: "0.00",
    compensation: "0.00",
    interest: "0.00",
  });
});

it("shows the reason when the backend refuses", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ detail: "This appeal has its outcome already" }),
          {
            status: 409,
          },
        ),
      ),
    ),
  );
  render(<RecordOutcomeForm claimId="CLM-1001" onRecorded={() => undefined} />);
  fireEvent.change(screen.getByLabelText(/ombudsman.s decision/), {
    target: { value: "not upheld" },
  });
  fillBasics();

  fireEvent.click(button());

  expect((await screen.findByRole("alert")).textContent).toBe(
    "This appeal has its outcome already",
  );
});
