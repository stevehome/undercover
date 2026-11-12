import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, expect, it } from "vitest";
import { Navigation } from "./Navigation";

afterEach(cleanup);

it("marks the page you are on", () => {
  render(
    <MemoryRouter initialEntries={["/improvement"]}>
      <Navigation />
    </MemoryRouter>,
  );

  expect(
    screen
      .getByRole("link", { name: "Improvement" })
      .getAttribute("aria-current"),
  ).toBe("page");
  expect(
    screen.getByRole("link", { name: "Queue" }).getAttribute("aria-current"),
  ).toBeNull();
});

it("marks the queue only on its own page", () => {
  render(
    <MemoryRouter initialEntries={["/"]}>
      <Navigation />
    </MemoryRouter>,
  );

  expect(
    screen.getByRole("link", { name: "Queue" }).getAttribute("aria-current"),
  ).toBe("page");
});
