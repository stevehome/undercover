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
import type { Handler, Setting } from "../types";
import { MeContext } from "../useMe";
import { SettingsPage } from "./SettingsPage";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  delete document.documentElement.dataset.theme;
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
  handler_id: "HND-02",
  name: "Marcus Oyelaran",
  can_approve_over_limit: false,
};

const settings: Setting[] = [
  {
    key: "round_spending_limit",
    label: "Spending limit for each round",
    group: "Improvement",
    unit: "dollars",
    value: "0.50",
    maximum: "100.00",
    changed_by: null,
    changed_on: null,
  },
  {
    key: "improver_agents_at_once",
    label: "Claim agents at once",
    group: "Improvement",
    unit: "agents",
    value: "25",
    maximum: "25",
    changed_by: "Dana Whitfield",
    changed_on: "2026-01-01T09:00:00+00:00",
  },
];

function show(handler: Handler) {
  const posts: { url: string; body: unknown }[] = [];
  const impl = (input: FetchInput, init?: RequestInit): Promise<Response> => {
    const url = requestUrl(input);
    if (init?.method === "POST") {
      posts.push({ url, body: JSON.parse(init.body as string) });
      return Promise.resolve(new Response("{}"));
    }
    if (url === "/api/models") {
      return Promise.resolve(
        new Response(
          JSON.stringify([
            {
              model: "openai/gpt-6-luna",
              reasoning_efforts: ["none", "low", "medium"],
              input_price_per_million: 0.1,
              output_price_per_million: 0.5,
            },
          ]),
        ),
      );
    }
    return Promise.resolve(new Response(JSON.stringify(settings)));
  };
  vi.stubGlobal("fetch", vi.fn(impl));
  render(
    <MeContext.Provider value={handler}>
      <SettingsPage />
    </MeContext.Provider>,
  );
  return posts;
}

it("shows the settings and the models allowed", async () => {
  show(dana);

  expect(await screen.findByText("Claim agents at once")).toBeDefined();
  expect(screen.getByText(/^Dana Whitfield, .*2026/)).toBeDefined();
  expect(screen.getByText("openai/gpt-6-luna")).toBeDefined();
  expect(screen.getByText("none, low, medium")).toBeDefined();
});

it("lets a senior handler change a setting after a confirmation", async () => {
  const posts = show(dana);
  const input = await screen.findByLabelText(
    "Improvement: Spending limit for each round",
  );

  fireEvent.change(input, { target: { value: "0.75" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0]);
  expect(posts).toHaveLength(0);
  expect(screen.getByRole("dialog")).toBeDefined();
  fireEvent.click(screen.getByRole("button", { name: "Change it" }));

  await waitFor(() => {
    expect(posts).toEqual([
      { url: "/api/settings/round_spending_limit", body: { value: "0.75" } },
    ]);
  });
});

it("changes nothing when the confirmation is cancelled", async () => {
  const posts = show(dana);
  const input = await screen.findByLabelText(
    "Improvement: Spending limit for each round",
  );

  fireEvent.change(input, { target: { value: "0.75" } });
  fireEvent.click(screen.getAllByRole("button", { name: "Save" })[0]);
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(posts).toHaveLength(0);
  expect(screen.queryByRole("dialog")).toBeNull();
});

it("shows a handler who can't change settings why, with nothing to edit", async () => {
  show(marcus);

  expect(await screen.findByText("Claim agents at once")).toBeDefined();
  expect(
    screen.getByText(/Marcus Oyelaran can't change settings/),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
  expect(screen.queryByRole("button", { name: "Save" })).toBeNull();
});

it("switches the appearance and the browser remembers it", async () => {
  show(marcus);
  await screen.findByText("Claim agents at once");

  fireEvent.click(screen.getByLabelText("Dark"));
  expect(document.documentElement.dataset.theme).toBe("dark");
  expect(localStorage.getItem("undercover-appearance")).toBe("dark");

  fireEvent.click(screen.getByLabelText("Light"));
  expect(document.documentElement.dataset.theme).toBe("light");
});
