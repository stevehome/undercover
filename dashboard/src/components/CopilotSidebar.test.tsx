import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import {
  card,
  conversation,
  conversationToWire,
  dana,
} from "../copilotFixtures";
import type { FetchInput } from "../testHelpers";
import { requestUrl } from "../testHelpers";
import type { Conversation } from "../types";
import { CopilotSidebar } from "./CopilotSidebar";

vi.mock("../auth", () => import("../testAuth"));

const BASE = "/api/copilot/conversations";
const OPEN = "undercover-copilot-open";
const SHOWN = "undercover-copilot-conversation";
const posts: { url: string; body: unknown }[] = [];
let chat: Conversation = conversation();

function serve(refuse = false) {
  vi.stubGlobal(
    "fetch",
    vi.fn((input: FetchInput, init?: RequestInit) => {
      const url = requestUrl(input);
      if (init?.method === "POST") {
        posts.push({ url, body: init.body });
        return Promise.resolve(
          refuse
            ? new Response(
                JSON.stringify({ detail: "The Copilot isn't running" }),
                {
                  status: 503,
                },
              )
            : new Response(JSON.stringify({ conversation_id: "copilot-1" }), {
                status: url === BASE ? 201 : 202,
              }),
        );
      }
      const body =
        url === BASE
          ? [
              {
                conversation_id: "copilot-1",
                title: chat.title,
                created_on: "x",
              },
            ]
          : conversationToWire(chat);
      return Promise.resolve(new Response(JSON.stringify(body)));
    }),
  );
}

const show = () =>
  render(
    <MemoryRouter>
      <CopilotSidebar me={dana} />
    </MemoryRouter>,
  );

const reopen = (conversation: Conversation) => {
  chat = conversation;
  localStorage.setItem(SHOWN, "copilot-1");
};

beforeEach(() => {
  posts.length = 0;
  chat = conversation();
  serve();
});

afterEach(() => {
  cleanup();
  localStorage.clear();
  vi.unstubAllGlobals();
});

it("is open the first time, with a greeting, the message box and who is signed in", async () => {
  show();

  expect(
    await screen.findByRole("heading", { name: "Hello, Dana" }),
  ).toBeDefined();
  expect(screen.getByLabelText("Ask the Copilot")).toBeDefined();
  expect(screen.getByText("Signed in as Dana Whitfield")).toBeDefined();
});

it("collapses to a slim tab, remembers it, and opens again", async () => {
  const first = show();
  await screen.findByRole("heading", { name: "Hello, Dana" });

  fireEvent.click(screen.getByRole("button", { name: "Collapse the Copilot" }));

  expect(screen.queryByLabelText("Ask the Copilot")).toBeNull();
  expect(localStorage.getItem(OPEN)).toBe("false");
  first.unmount();

  show();
  expect(screen.queryByLabelText("Ask the Copilot")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Open the Copilot" }));

  expect(await screen.findByLabelText("Ask the Copilot")).toBeDefined();
});

it("makes a conversation for a first message and sends it", async () => {
  show();
  await screen.findByRole("heading", { name: "Hello, Dana" });

  fireEvent.click(
    screen.getByRole("button", { name: "What needs a handler?" }),
  );

  await waitFor(() => {
    expect(posts.map((post) => post.url)).toEqual([
      BASE,
      `${BASE}/copilot-1/messages`,
    ]);
  });
  expect(posts[1].body).toBe(JSON.stringify({ text: "What needs a handler?" }));
});

it("picks up the conversation it showed last time, with its steps", async () => {
  reopen(conversation());

  show();

  expect(await screen.findByText("get_claim")).toBeDefined();
  expect(screen.getByText("Who needs me?", { selector: "p" })).toBeDefined();
});

it("keeps the waiting card after a reload, and sends the handler's answer", async () => {
  reopen(conversation({ status: "waiting for a confirmation", card }));
  show();

  fireEvent.click(
    await screen.findByRole("button", { name: "Sign off and pay" }),
  );

  await waitFor(() => {
    expect(posts.at(-1)?.url).toBe(`${BASE}/copilot-1/confirmation`);
  });
  expect(posts.at(-1)?.body).toBe(JSON.stringify({ confirmed: true }));
});

it("asks for the confirmation first while one waits", async () => {
  reopen(conversation({ status: "waiting for a confirmation", card }));
  show();

  const box = await screen.findByLabelText("Ask the Copilot");

  expect(box.getAttribute("placeholder")).toBe("Answer the confirmation first");
});

it("starts a new conversation from the list", async () => {
  reopen(conversation());
  show();
  await screen.findByText("get_claim");

  fireEvent.click(screen.getByRole("button", { name: "New conversation" }));

  expect(
    await screen.findByRole("heading", { name: "Hello, Dana" }),
  ).toBeDefined();
  await waitFor(() => {
    expect(localStorage.getItem(SHOWN)).toBeNull();
  });
});

it("shows the reason a message was refused", async () => {
  serve(true);
  reopen(conversation());
  show();

  fireEvent.change(await screen.findByLabelText("Ask the Copilot"), {
    target: { value: "Hello" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));

  expect((await screen.findByRole("alert")).textContent).toBe(
    "The Copilot isn't running",
  );
});
