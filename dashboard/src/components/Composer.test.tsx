import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { TurnStatus } from "../types";
import { Composer } from "./Composer";

afterEach(cleanup);

function show(status: TurnStatus | null = "done") {
  const onSend = vi.fn();
  render(<Composer status={status} onSend={onSend} />);
  return { onSend, box: screen.getByLabelText("Ask the Copilot") };
}

it("sends on Enter and clears the box", () => {
  const { onSend, box } = show();
  fireEvent.change(box, { target: { value: "  Who needs me?  " } });

  fireEvent.keyDown(box, { key: "Enter" });

  expect(onSend).toHaveBeenCalledWith("Who needs me?");
  expect((box as HTMLTextAreaElement).value).toBe("");
});

it("starts a new line on Shift+Enter instead of sending", () => {
  const { onSend, box } = show();
  fireEvent.change(box, { target: { value: "one" } });

  fireEvent.keyDown(box, { key: "Enter", shiftKey: true });

  expect(onSend).not.toHaveBeenCalled();
});

it("sends nothing when the box is empty", () => {
  const { onSend, box } = show();

  fireEvent.keyDown(box, { key: "Enter" });
  fireEvent.click(screen.getByRole("button", { name: "Send" }));

  expect(onSend).not.toHaveBeenCalled();
});

it("sends with the Send button", () => {
  const { onSend, box } = show();
  fireEvent.change(box, { target: { value: "Hello" } });

  fireEvent.click(screen.getByRole("button", { name: "Send" }));

  expect(onSend).toHaveBeenCalledWith("Hello");
});

it.each<[TurnStatus, string]>([
  ["working", "The Copilot is working"],
  ["waiting for a confirmation", "Answer the confirmation first"],
])("is off while the status is %s, and says why", (status, why) => {
  const { onSend, box } = show(status);

  expect((box as HTMLTextAreaElement).disabled).toBe(true);
  expect(box.getAttribute("placeholder")).toBe(why);
  expect(
    screen.getByRole<HTMLButtonElement>("button", { name: "Send" }).disabled,
  ).toBe(true);
  expect(onSend).not.toHaveBeenCalled();
});

it.each<TurnStatus | null>(["done", "failed", "stopped", null])(
  "is on when the status is %s",
  (status) => {
    const { box } = show(status);

    expect((box as HTMLTextAreaElement).disabled).toBe(false);
  },
);
