import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { FileSource, Step } from "../types";
import { StepList } from "./StepList";

afterEach(cleanup);

const source: FileSource = {
  system: "Policy administration",
  owner: "Product",
  reviewed: "2026-09-01",
};

const steps: Step[] = [
  {
    recorded_on: "1",
    kind: "note",
    text: "Security check: no instructions found",
  },
  {
    recorded_on: "2",
    kind: "tool_call",
    text: "Called undercover-context___get_plan",
    tool: "undercover-context___get_plan",
  },
  {
    recorded_on: "3",
    kind: "lookup",
    text: "Looked up the premium plan",
    files: { "plans.yaml": source },
  },
  {
    recorded_on: "4",
    kind: "memory_search",
    text: "Searched the customer's memory for bags",
    found: ["Earlier: lost a bag."],
  },
  {
    recorded_on: "5",
    kind: "memory_save",
    text: "Saved the claim and its decision to the customer's memory",
    saved: ["Claim CLM-1005: a delay."],
  },
  {
    recorded_on: "6",
    kind: "refusal",
    text: "Refused by the Gateway: Tool Execution Denied",
    source: "the Gateway",
    detail: "Tool Execution Denied",
  },
];

it("shows nothing when the agent has done nothing yet", () => {
  render(<StepList steps={[]} />);

  expect(screen.queryByText("What the agent did")).toBeNull();
});

it("shows each step in order under one heading", () => {
  render(<StepList steps={steps} />);

  expect(screen.getByText("What the agent did")).toBeDefined();
  const items = screen.getAllByRole("listitem");
  expect(items[0].textContent).toBe("Security check: no instructions found");
  expect(items[1].textContent).toBe("Called undercover-context___get_plan");
});

it("names a tool call as its route names it, in the code font", () => {
  render(<StepList steps={steps} />);

  const call = screen.getByText("Called undercover-context___get_plan");
  expect(call.className).toBe("mono");
});

it("shows what a lookup asked and the file it came from", () => {
  render(<StepList steps={steps} />);

  expect(screen.getByText("Looked up the premium plan")).toBeDefined();
  expect(screen.getByText("plans.yaml").className).toBe("mono");
});

it("lists what a memory search found and what a save kept", () => {
  render(<StepList steps={steps} />);

  expect(screen.getByText("Earlier: lost a bag.")).toBeDefined();
  expect(screen.getByText("Claim CLM-1005: a delay.")).toBeDefined();
});

it("says when a memory search found nothing", () => {
  render(
    <StepList
      steps={[
        {
          recorded_on: "1",
          kind: "memory_search",
          text: "Searched the customer's memory for dogs",
          found: [],
        },
      ]}
    />,
  );

  expect(screen.getByText("Found nothing.")).toBeDefined();
});

it("makes a refusal stand out and says who refused it", () => {
  render(<StepList steps={steps} />);

  const refusal = screen.getByText("Refused by the Gateway").closest("li");
  expect(refusal?.className).toContain("refusal");
  expect(refusal?.textContent).toContain("Tool Execution Denied");
  expect(
    screen
      .getAllByRole("listitem")
      .filter((li) => li.className.includes("refusal")),
  ).toHaveLength(1);
});
