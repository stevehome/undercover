import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import {
  finishedRound,
  wireProposal,
  wireRound,
  wireScores,
} from "../roundFixtures";
import { requestUrl } from "../testHelpers";
import type { FetchInput } from "../testHelpers";
import type { Handler } from "../types";
import { MeContext } from "../useMe";
import { ImprovementPage } from "./ImprovementPage";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const dana: Handler = {
  handler_id: "HND-01",
  name: "Dana Whitfield",
  role: "Senior Claims Handler",
  email: "dana.whitfield@undercover.example",
  can_approve_over_limit: true,
};
const marcus: Handler = {
  ...dana,
  name: "Marcus Oyelaran",
  can_approve_over_limit: false,
};

const version = (number: number, accuracy: string) => ({
  version: number,
  instructions: "Decide.",
  model: "openai/gpt-6-luna",
  reasoning_effort: "low",
  reason: "A version",
  proposed_by: "improver",
  approved_by: null,
  approved_on: null,
  round_id: null,
  verdict: "kept",
  verdict_reason: null,
  created_on: "2026-01-01T00:00:00+00:00",
  held_out: wireScores(accuracy, "1.500"),
});

const recipe = {
  version: 1,
  text: "1. Read.",
  reason: "The starting version",
  proposed_by: "seed",
  approved_by: null,
  verdict: "kept",
  created_on: "2026-01-01T00:00:00+00:00",
};

function show(
  handler: Handler,
  rounds: unknown[],
  answer = () => new Response("{}"),
) {
  const posts: { url: string; body: unknown }[] = [];
  const impl = (input: FetchInput, init?: RequestInit): Promise<Response> => {
    const url = requestUrl(input);
    if (init?.method === "POST") {
      posts.push({
        url,
        body: init.body ? JSON.parse(init.body as string) : null,
      });
      return Promise.resolve(answer());
    }
    const body = {
      "/api/rounds": rounds,
      "/api/configurations": [version(1, "0.7200"), version(2, "0.8400")],
      "/api/recipes": [recipe],
    }[url] ?? {
      version: 1,
      from_version: null,
      lines: [{ kind: "added", text: "1. Read." }],
    };
    return Promise.resolve(new Response(JSON.stringify(body)));
  };
  vi.stubGlobal("fetch", vi.fn(impl));
  render(
    <MeContext.Provider value={handler}>
      <ImprovementPage />
    </MeContext.Provider>,
  );
  return posts;
}

const waiting = wireRound({
  stage: "change waiting",
  proposals: [wireProposal],
});

it("lists the rounds with what each tried and what came of it", async () => {
  show(dana, [finishedRound]);

  const row = (await screen.findByText("Add a rule for late claims.")).closest(
    "tr",
  );
  expect(row?.textContent).toContain("72.0% to 84.0%");
  expect(row?.textContent).toContain("1.40 to 1.70");
  expect(row?.textContent).toContain("accuracy improved");
  expect(row?.textContent).toContain("change approved by Dana Whitfield");
  expect(row?.textContent).toContain("$0.0123");
});

it("shows a round that proposed nothing with no version tried", async () => {
  show(dana, [wireRound({ round_id: 4, stage: "finished" })]);

  const row = (await screen.findByText(/^Dana Whitfield, /)).closest("tr");
  expect(row?.cells[4].textContent).toBe("–");
});

it("shows the newest round first", async () => {
  show(dana, [wireRound({ round_id: 5, stage: "finished" }), finishedRound]);

  await screen.findByText("Add a rule for late claims.");
  const ids = screen
    .getAllByRole("row")
    .slice(1)
    .map((row) => (row as HTMLTableRowElement).cells[0].textContent);
  expect(ids.slice(0, 2)).toEqual(["5", "1"]);
});

it("shows where the open round has got to, and the proposal waiting", async () => {
  show(dana, [waiting]);

  expect(
    await screen.findByText("A change is waiting for approval", {
      selector: "h2",
    }),
  ).toBeDefined();
  expect(
    screen.getByText(/proposed openai\/gpt-6-luna at medium/),
  ).toBeDefined();
  expect(
    screen.getByText("Decide the claim, and never approve a late one."),
  ).toBeDefined();
  expect(screen.getByText(/Late claims were approved/)).toBeDefined();
});

it("sends an approval to the agent's service after a confirmation", async () => {
  const posts = show(dana, [waiting]);
  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  expect(posts).toHaveLength(0);

  fireEvent.click(within_dialog("Approve"));

  await waitFor(() => {
    expect(posts).toEqual([
      {
        url: "/api/proposals/3/decision",
        body: { decision: "approve", reason: "" },
      },
    ]);
  });
});

function within_dialog(name: string) {
  const dialog = screen.getByRole("dialog");
  return Array.from(dialog.querySelectorAll("button")).find(
    (button) => button.textContent === name,
  ) as HTMLElement;
}

it("needs a reason to reject, and sends it", async () => {
  const posts = show(dana, [waiting]);
  const reject = await screen.findByRole("button", { name: "Reject" });
  expect((reject as HTMLButtonElement).disabled).toBe(true);

  fireEvent.change(screen.getByLabelText(/Why you are rejecting it/), {
    target: { value: "Too long." },
  });
  fireEvent.click(reject);
  fireEvent.click(within_dialog("Reject"));

  await waitFor(() => {
    expect(posts).toEqual([
      {
        url: "/api/proposals/3/decision",
        body: { decision: "reject", reason: "Too long." },
      },
    ]);
  });
});

it("shows a handler who can't approve why, with no buttons", async () => {
  show(marcus, [waiting]);

  expect(
    await screen.findByText(/Marcus Oyelaran can't approve or reject this/),
  ).toBeDefined();
  expect(screen.queryByRole("button", { name: "Approve" })).toBeNull();
  expect(screen.queryByRole("button", { name: "Start a round" })).toBeNull();
  expect(screen.getByText(/can't start or stop a round/)).toBeDefined();
});

it("shows the reason when the backend refuses", async () => {
  show(
    dana,
    [waiting],
    () =>
      new Response('{"detail":"A dispatch is already running"}', {
        status: 409,
      }),
  );
  fireEvent.click(await screen.findByRole("button", { name: "Approve" }));
  fireEvent.click(within_dialog("Approve"));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "A dispatch is already running",
  );
});

it("starts a round after a confirmation", async () => {
  const posts = show(dana, [finishedRound]);

  fireEvent.click(await screen.findByRole("button", { name: "Start a round" }));
  fireEvent.click(within_dialog("Start the round"));

  await waitFor(() => {
    expect(posts).toEqual([{ url: "/api/rounds", body: null }]);
  });
});

it("stops the open round after a confirmation, and can't start another", async () => {
  const posts = show(dana, [waiting]);

  const start = await screen.findByRole("button", { name: "Start a round" });
  expect((start as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "Stop round 2" }));
  fireEvent.click(within_dialog("Stop it"));

  await waitFor(() => {
    expect(posts).toEqual([{ url: "/api/rounds/2/stop", body: null }]);
  });
});

it("plots the versions and lists the recipe's versions with their changes", async () => {
  show(dana, [finishedRound]);

  expect(
    await screen.findByRole("img", { name: /accuracy and grade/ }),
  ).toBeDefined();
  fireEvent.click(await screen.findByRole("button", { name: "Show changes" }));
  expect(
    await screen.findByText("Recipe version 1: what it changed"),
  ).toBeDefined();
});

it("says there are no rounds yet", async () => {
  show(dana, []);

  expect(await screen.findByText(/No rounds yet/)).toBeDefined();
});
