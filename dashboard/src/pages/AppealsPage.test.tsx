import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { appeal, appealToWire, upheld } from "../appealFixtures";
import { requestUrl } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import { AppealsPage } from "./AppealsPage";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const figures = {
  open: 1,
  upheld: 1,
  not_upheld: 0,
  upheld_share: "1.0000",
  redress_paid: "0.00",
  redress_waiting: "217.10",
};

function serve(appeals: unknown[], shown = figures) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: FetchInput) => {
      const body = requestUrl(input) === "/api/appeals" ? appeals : shown;
      return Promise.resolve(new Response(JSON.stringify(body)));
    }),
  );
}

const open = () =>
  render(
    <MemoryRouter>
      <AppealsPage />
    </MemoryRouter>,
  );

it("shows the figures and every appeal, each linking to its claim", async () => {
  serve([
    appealToWire(appeal({ claim_id: "CLM-1607" })),
    appealToWire(upheld({ claim_id: "CLM-1602" })),
  ]);

  open();

  expect(await screen.findByText("Redress waiting")).toBeTruthy();
  expect(screen.getByText("100.0%")).toBeTruthy();
  expect(screen.getByText("$217.10", { selector: "dd" })).toBeTruthy();
  const rows = screen.getAllByRole("row").slice(1);
  expect(rows).toHaveLength(2);
  expect(
    within(rows[0])
      .getByRole("link", { name: "CLM-1607" })
      .getAttribute("href"),
  ).toBe("/claims/CLM-1607");
  expect(
    within(rows[1]).getByText("appeal upheld, redress waiting"),
  ).toBeTruthy();
  expect(within(rows[1]).getByText("$217.10")).toBeTruthy();
});

it("filters the appeals by status", async () => {
  serve([
    appealToWire(appeal({ claim_id: "CLM-1607" })),
    appealToWire(upheld({ claim_id: "CLM-1602" })),
  ]);
  open();
  await screen.findByText("CLM-1607");

  fireEvent.change(screen.getByLabelText(/Show/), {
    target: { value: "upheld" },
  });

  expect(screen.queryByText("CLM-1607")).toBeNull();
  expect(screen.getByText("CLM-1602")).toBeTruthy();

  fireEvent.change(screen.getByLabelText(/Show/), {
    target: { value: "not upheld" },
  });

  expect(screen.getByText("No appeals have this status.")).toBeTruthy();
});

it("says how to record one when there are none, with no share yet", async () => {
  serve([], { ...figures, open: 0, upheld: 0, upheld_share: null as never });

  open();

  expect(await screen.findByText(/No appeals yet/)).toBeTruthy();
  expect(screen.getAllByText("–").length).toBeGreaterThan(0);
});

it("says so when the appeals can't be loaded", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response("", { status: 500 }))),
  );

  open();

  await waitFor(() => {
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
