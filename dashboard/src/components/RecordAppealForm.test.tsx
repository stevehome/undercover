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
import { RecordAppealForm } from "./RecordAppealForm";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function fill() {
  fireEvent.change(screen.getByLabelText(/ombudsman.s reference/), {
    target: { value: "  OMB-1  " },
  });
  fireEvent.change(screen.getByLabelText(/date it reached us/), {
    target: { value: "2026-11-20" },
  });
  fireEvent.change(screen.getByLabelText(/customer.s grounds/), {
    target: { value: "  The ferry was late.  " },
  });
}

it("needs the reference, the date and the grounds before it records", () => {
  render(<RecordAppealForm claimId="CLM-1001" onRecorded={() => undefined} />);
  const button = screen.getByRole("button", { name: "Record the appeal" });
  expect((button as HTMLButtonElement).disabled).toBe(true);

  fill();

  expect((button as HTMLButtonElement).disabled).toBe(false);
});

it("records the appeal with the texts trimmed, then says it is recorded", async () => {
  const calls: { url: string; body: string }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: FetchInput, init?: RequestInit) => {
      calls.push({
        url: requestUrl(input),
        body: typeof init?.body === "string" ? init.body : "",
      });
      return Promise.resolve(new Response("{}"));
    }),
  );
  const recorded = vi.fn();
  render(<RecordAppealForm claimId="CLM-1001" onRecorded={recorded} />);
  fill();

  fireEvent.click(screen.getByRole("button", { name: "Record the appeal" }));

  await waitFor(() => {
    expect(recorded).toHaveBeenCalled();
  });
  expect(calls).toEqual([
    {
      url: "/api/claims/CLM-1001/appeal",
      body: JSON.stringify({
        ombudsman_reference: "OMB-1",
        received_on: "2026-11-20",
        grounds: "The ferry was late.",
      }),
    },
  ]);
});

it("shows the reason when the backend refuses", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify({ detail: "This claim already has an appeal" }),
          {
            status: 409,
          },
        ),
      ),
    ),
  );
  render(<RecordAppealForm claimId="CLM-1001" onRecorded={() => undefined} />);
  fill();

  fireEvent.click(screen.getByRole("button", { name: "Record the appeal" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "This claim already has an appeal",
  );
});
