import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { requestUrl, wireEvaluation } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import { ScoreboardPage } from "./ScoreboardPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function stubFetch() {
  const posted: unknown[] = [];
  const impl = (input: FetchInput, init?: RequestInit): Promise<Response> => {
    if (init?.method === "POST") {
      posted.push(JSON.parse(init.body as string));
      return Promise.resolve(new Response('{"run_id":8}'));
    }
    const url = requestUrl(input);
    const body = url.endsWith("/api/evaluations")
      ? [wireEvaluation]
      : wireEvaluation;
    return Promise.resolve(new Response(JSON.stringify(body)));
  };
  vi.stubGlobal("fetch", vi.fn(impl));
  return posted;
}

function renderPage() {
  render(
    <MemoryRouter>
      <ScoreboardPage />
    </MemoryRouter>,
  );
}

it("lists an evaluation with every measure", async () => {
  stubFetch();

  renderPage();

  const row = (await screen.findByText("The held-out set, tiny")).closest("tr");
  expect(row?.textContent).toContain("80.0%");
  expect(row?.textContent).toContain("1.80");
  expect(row?.textContent).toContain("60.0%");
  expect(row?.textContent).toContain("$1,550.00");
  expect(row?.textContent).toContain("$0.0006");
  expect(row?.textContent).toContain("27.9 s");
  expect(row?.textContent).toContain("30.0 s");
  expect(
    screen.getByRole("link", { name: /2026|Jan/ }).getAttribute("href"),
  ).toBe("/evaluations/7");
});

it("starts an evaluation with the chosen number, set and size", async () => {
  const posted = stubFetch();
  renderPage();
  const number = await screen.findByLabelText("Claim agents at once");
  expect((number as HTMLInputElement).value).toBe("5");

  fireEvent.click(screen.getByRole("button", { name: "Start an evaluation" }));
  fireEvent.change(number, { target: { value: "25" } });
  fireEvent.change(screen.getByLabelText("Set"), {
    target: { value: "held_out" },
  });
  fireEvent.click(screen.getByLabelText("Only the 5 tiny claims"));
  fireEvent.click(screen.getByRole("button", { name: "Start an evaluation" }));
  await waitFor(() => {
    expect(posted).toHaveLength(2);
  });

  expect(posted).toEqual([
    { concurrency: 5, eval_set: "evaluation", tiny: false },
    { concurrency: 25, eval_set: "held_out", tiny: true },
  ]);
});

it("shows the round that started an evaluation, or a dash for one started by hand", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(
        new Response(
          JSON.stringify([
            { ...wireEvaluation, run_id: 9, round_id: 3 },
            wireEvaluation,
          ]),
        ),
      ),
    ),
  );

  renderPage();

  await screen.findAllByText("The held-out set, tiny");
  const roundCells = screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => row.querySelectorAll("td")[1].textContent);
  expect(roundCells).toEqual(["3", "–"]);
});
