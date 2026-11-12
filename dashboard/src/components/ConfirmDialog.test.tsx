import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ConfirmDialog } from "./ConfirmDialog";

afterEach(cleanup);

function show(onConfirm = vi.fn(), onCancel = vi.fn()) {
  render(
    <ConfirmDialog
      title="Change the limit?"
      confirmLabel="Change it"
      onConfirm={onConfirm}
      onCancel={onCancel}
    >
      <p>It is recorded.</p>
    </ConfirmDialog>,
  );
  return { onConfirm, onCancel };
}

it("is open with its title and what it will do", () => {
  show();

  expect(
    screen.getByRole("dialog", { name: "Change the limit?" }),
  ).toBeDefined();
  expect(screen.getByText("It is recorded.")).toBeDefined();
});

it("confirms or cancels", () => {
  const { onConfirm, onCancel } = show();

  fireEvent.click(screen.getByRole("button", { name: "Change it" }));
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(onConfirm).toHaveBeenCalledOnce();
  expect(onCancel).toHaveBeenCalledOnce();
});

it("cancels when escape closes it", () => {
  const { onCancel } = show();

  fireEvent(
    screen.getByRole("dialog"),
    new Event("cancel", { cancelable: true }),
  );

  expect(onCancel).toHaveBeenCalledOnce();
});
