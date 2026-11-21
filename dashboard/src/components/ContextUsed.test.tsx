import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import type { FileSource, Step } from "../types";
import { ContextUsed } from "./ContextUsed";

afterEach(cleanup);

const plans: FileSource = {
  system: "Policy administration",
  owner: "Product",
  reviewed: "2026-09-01",
};
const manual: FileSource = {
  system: "Claims operations",
  owner: "Head of claims operations",
  reviewed: "2026-09-01",
};

function lookup(
  at: string,
  text: string,
  files: Record<string, FileSource>,
): Step {
  return { recorded_on: at, kind: "lookup", text, files };
}

it("shows nothing when the agent looked nothing up", () => {
  render(
    <ContextUsed
      steps={[{ recorded_on: "1", kind: "note", text: "Read the claim" }]}
    />,
  );

  expect(screen.queryByText("Context used")).toBeNull();
});

it("groups what was looked up by file, with each file's source", () => {
  render(
    <ContextUsed
      steps={[
        lookup("1", "Looked up the premium plan", { "plans.yaml": plans }),
        lookup("2", "Read claims manual section 14: Records", {
          "claims_manual.md": manual,
        }),
      ]}
    />,
  );

  expect(screen.getByText("Context used")).toBeDefined();
  expect(screen.getByText("plans.yaml")).toBeDefined();
  expect(
    screen.getByText(/Policy administration, owned by Product/),
  ).toBeDefined();
  expect(screen.getByText("claims_manual.md")).toBeDefined();
  expect(
    screen.getByText(/Claims operations, owned by Head of claims operations/),
  ).toBeDefined();
});

it("lists a lookup made twice once", () => {
  render(
    <ContextUsed
      steps={[
        lookup("1", "Looked up the premium plan", { "plans.yaml": plans }),
        lookup("2", "Looked up the premium plan", { "plans.yaml": plans }),
        lookup("3", "Looked up the first plan", { "plans.yaml": plans }),
      ]}
    />,
  );

  expect(screen.getAllByText("Looked up the premium plan")).toHaveLength(1);
  expect(screen.getAllByText("plans.yaml")).toHaveLength(1);
  expect(screen.getByText("Looked up the first plan")).toBeDefined();
});

it("files a search that drew on two files under each", () => {
  render(
    <ContextUsed
      steps={[
        lookup("1", "Searched the documents for sign off", {
          "policy_wording.md": plans,
          "claims_manual.md": manual,
        }),
      ]}
    />,
  );

  expect(
    screen.getAllByText("Searched the documents for sign off"),
  ).toHaveLength(2);
});
