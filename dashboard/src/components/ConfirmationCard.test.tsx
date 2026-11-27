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

const redressCard = {
  kind: "redress",
  claim_id: "CLM-1602",
  customer: { customer_id: "CUS-3408", name: "Gareth Ollander" },
  redress: {
    claim_amount: 40000,
    compensation: 15000,
    interest: 640,
    total: 55640,
  },
  reason: "The wording was unclear.",
} as const;

it("shows a redress card with its three amounts, the total and the ombudsman's reason", () => {
  render(
    <MemoryRouter>
      <ConfirmationCard card={redressCard} onAnswer={() => undefined} />
    </MemoryRouter>,
  );

  const region = screen.getByRole("region", { name: "Confirm the redress" });
  expect(region.textContent).toContain("Gareth Ollander");
  for (const amount of ["$400.00", "$150.00", "$6.40", "$556.40"]) {
    expect(region.textContent).toContain(amount);
  }
  expect(region.textContent).toContain("The wording was unclear.");
});

it("leaves out the reason of a marked appeal, and answers Pay redress or Cancel", () => {
  const answers: boolean[] = [];
  render(
    <MemoryRouter>
      <ConfirmationCard
        card={{ ...redressCard, reason: null }}
        onAnswer={(confirmed) => answers.push(confirmed)}
      />
    </MemoryRouter>,
  );

  expect(screen.queryByText("The ombudsman's reason")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
  fireEvent.click(screen.getByRole("button", { name: "Pay redress" }));

  expect(answers).toEqual([false, true]);
});
