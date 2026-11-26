import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ConversationList } from "./ConversationList";

afterEach(cleanup);

const earlier = [
  { conversation_id: "c-2", title: "Newer question", created_on: "2026-01-02" },
  { conversation_id: "c-1", title: null, created_on: "2026-01-01" },
];

it("lists the earlier conversations in the order given, marking the current one", () => {
  render(
    <ConversationList conversations={earlier} current="c-2" onPick={vi.fn()} />,
  );

  const items = screen.getAllByRole("listitem");
  expect(items.map((item) => item.textContent)).toEqual([
    "Newer question",
    "A new conversation",
  ]);
  expect(screen.getByText("Newer question").getAttribute("aria-current")).toBe(
    "true",
  );
});

it("opens one when it is picked", () => {
  const onPick = vi.fn();
  render(
    <ConversationList conversations={earlier} current={null} onPick={onPick} />,
  );

  fireEvent.click(screen.getByText("Newer question"));

  expect(onPick).toHaveBeenCalledWith("c-2");
});

it("starts a new conversation", () => {
  const onPick = vi.fn();
  render(
    <ConversationList conversations={earlier} current="c-2" onPick={onPick} />,
  );

  fireEvent.click(screen.getByRole("button", { name: "New conversation" }));

  expect(onPick).toHaveBeenCalledWith(null);
});
