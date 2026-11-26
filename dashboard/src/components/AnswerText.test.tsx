import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it } from "vitest";
import { AnswerText } from "./AnswerText";

afterEach(cleanup);

const show = (text: string) =>
  render(
    <MemoryRouter>
      <AnswerText text={text} />
    </MemoryRouter>,
  );

it("shows a table formatted", () => {
  show("| Claim | Payout |\n| --- | --- |\n| CLM-1003 | $3,750.00 |");

  expect(screen.getByRole("table")).toBeDefined();
  expect(screen.getByRole("columnheader", { name: "Payout" })).toBeDefined();
});

it("shows a list formatted", () => {
  show("- first\n- second");

  expect(screen.getAllByRole("listitem")).toHaveLength(2);
});

it("links a claim id to the claim's page, in a sentence and in a table", () => {
  show("CLM-1003 needs you.\n\n| Claim |\n| --- |\n| CLM-1004 |");

  expect(
    screen.getByRole("link", { name: "CLM-1003" }).getAttribute("href"),
  ).toBe("/claims/CLM-1003");
  expect(
    screen.getByRole("link", { name: "CLM-1004" }).getAttribute("href"),
  ).toBe("/claims/CLM-1004");
});

it("doesn't link a claim id twice when the model already linked it", () => {
  show("See [CLM-1003](/claims/CLM-1003).");

  expect(screen.getAllByRole("link")).toHaveLength(1);
});

it("shows raw HTML as text and never as markup", () => {
  const { container } = show("<img src=x onerror=alert(1)> <b>bold</b>");

  expect(container.querySelector("img")).toBeNull();
  expect(container.querySelector("b")).toBeNull();
  expect(container.textContent).toContain("<b>bold</b>");
});

it("opens another link in a new tab", () => {
  show("[Docs](https://example.com)");

  expect(
    screen.getByRole("link", { name: "Docs" }).getAttribute("target"),
  ).toBe("_blank");
});
