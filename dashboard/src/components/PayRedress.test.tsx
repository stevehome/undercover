import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { dana, marcus } from "../appealFixtures";
import { requestUrl } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import { MeContext } from "../useMe";
import { PayRedress } from "./PayRedress";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const redress = {
  claim_amount: 14000,
  compensation: 7500,
  interest: 210,
  total: 21710,
};

function stubFetch(status = 200, body: unknown = {}) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: FetchInput) => {
      calls.push(requestUrl(input));
      return Promise.resolve(new Response(JSON.stringify(body), { status }));
    }),
  );
  return calls;
}

function show(handler = dana, onPaid = () => undefined) {
  render(
    <MeContext.Provider value={handler}>
      <PayRedress claimId="CLM-1601" redress={redress} onPaid={onPaid} />
    </MeContext.Provider>,
  );
}

it("asks a senior handler to confirm, then pays", async () => {
  const calls = stubFetch();
  const paid = vi.fn();
  show(dana, paid);

  fireEvent.click(
    screen.getByRole("button", { name: "Pay redress as Dana Whitfield" }),
  );
  const dialog = screen.getByRole("dialog", {
    name: "Pay the redress on CLM-1601?",
  });
  expect(within(dialog).getByText("$217.10")).toBeTruthy();
  expect(calls).toEqual([]);
  fireEvent.click(within(dialog).getByRole("button", { name: "Pay redress" }));

  await waitFor(() => {
    expect(paid).toHaveBeenCalled();
  });
  expect(calls).toEqual(["/api/claims/CLM-1601/appeal/redress"]);
});

it("pays nothing when the handler cancels", () => {
  const calls = stubFetch();
  show();

  fireEvent.click(
    screen.getByRole("button", { name: "Pay redress as Dana Whitfield" }),
  );
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", { name: "Cancel" }),
  );

  expect(calls).toEqual([]);
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("says why a handler who can't sign off can't pay", () => {
  show(marcus);

  expect(
    screen.getByText(/Marcus Oyelaran can't pay this redress/),
  ).toBeTruthy();
  expect(screen.queryByRole("button")).toBeNull();
});

it("shows the reason when the payment is refused", async () => {
  stubFetch(409, { detail: "The redress has already been paid" });
  show();

  fireEvent.click(
    screen.getByRole("button", { name: "Pay redress as Dana Whitfield" }),
  );
  fireEvent.click(
    within(screen.getByRole("dialog")).getByRole("button", {
      name: "Pay redress",
    }),
  );

  expect((await screen.findByRole("alert")).textContent).toBe(
    "The redress has already been paid",
  );
});
