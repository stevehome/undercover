import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { card, conversation, dana, step } from "../copilotFixtures";
import { SUGGESTIONS } from "../suggestions";
import type { Conversation as Chat } from "../types";
import { Conversation } from "./Conversation";

afterEach(cleanup);

function show(chat: Chat | null, onAsk = vi.fn(), onAnswer = vi.fn()) {
  render(
    <MemoryRouter>
      <Conversation
        conversation={chat}
        me={dana}
        onAsk={onAsk}
        onAnswer={onAnswer}
      />
    </MemoryRouter>,
  );
  return { onAsk, onAnswer };
}

it("greets an empty conversation by first name and offers suggested questions", () => {
  const { onAsk } = show(null);

  expect(screen.getByRole("heading", { name: "Hello, Dana" })).toBeDefined();
  for (const suggestion of SUGGESTIONS) {
    expect(screen.getByRole("button", { name: suggestion })).toBeDefined();
  }

  fireEvent.click(screen.getByRole("button", { name: SUGGESTIONS[1] }));

  expect(onAsk).toHaveBeenCalledWith(SUGGESTIONS[1]);
});

it("shows each message with its steps and the answer's usage in small print", () => {
  show(conversation());

  expect(screen.getByText("Who needs me?")).toBeDefined();
  expect(screen.getByText("get_claim")).toBeDefined();
  expect(screen.getByRole("link", { name: "CLM-1003" })).toBeDefined();
  expect(screen.getByText("2 model calls, $0.0006, 2.5 s")).toBeDefined();
});

it("says call, not calls, for one", () => {
  const chat = conversation();
  chat.messages[1].model_calls = 1;
  chat.messages[1].cost_nanos = null;
  chat.messages[1].seconds = null;

  show(chat);

  expect(screen.getByText("1 model call")).toBeDefined();
});

it("shows a working indicator while the Copilot works", () => {
  show(conversation({ status: "working", steps: [step("working")] }));

  expect(screen.getByRole("status").textContent).toContain("Working");
});

it("shows no working indicator when the turn is done", () => {
  show(conversation());

  expect(screen.queryByRole("status")).toBeNull();
});

it("says a stopped turn stopped, so the handler can ask again", () => {
  show(conversation({ status: "stopped" }));

  expect(screen.getByText(/That turn stopped without an answer/)).toBeDefined();
});

it("shows the confirmation a turn waits for, and passes the answer on", () => {
  const { onAnswer } = show(
    conversation({ status: "waiting for a confirmation", card }),
  );

  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));

  expect(screen.getByText("Sign off this payout?")).toBeDefined();
  expect(onAnswer).toHaveBeenCalledWith(true);
});
