import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { card } from "../copilotFixtures";
import { ConfirmationCard } from "./ConfirmationCard";

afterEach(cleanup);

function show(onAnswer = vi.fn()) {
  render(
    <MemoryRouter>
      <ConfirmationCard card={card} onAnswer={onAnswer} />
    </MemoryRouter>,
  );
  return onAnswer;
}

it("shows the claim, the customer, what it will pay and the agent's reason", () => {
  show();

  expect(
    screen.getByRole("link", { name: "CLM-1003" }).getAttribute("href"),
  ).toBe("/claims/CLM-1003");
  expect(screen.getByText("Ana Souza")).toBeDefined();
  expect(screen.getByText("$3,750.00")).toBeDefined();
  expect(screen.getByText("Covered by section 3.")).toBeDefined();
});

it("answers yes with Sign off and pay", () => {
  const onAnswer = show();

  fireEvent.click(screen.getByRole("button", { name: "Sign off and pay" }));

  expect(onAnswer).toHaveBeenCalledWith(true);
});

it("answers no with Cancel", () => {
  const onAnswer = show();

  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));

  expect(onAnswer).toHaveBeenCalledWith(false);
});
