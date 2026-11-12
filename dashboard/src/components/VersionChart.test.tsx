import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { VersionChart } from "./VersionChart";

afterEach(cleanup);

it("plots each version and gives the same numbers in a table", () => {
  const { container } = render(
    <VersionChart
      points={[
        { version: 1, accuracy: 0.72, grade: 1.4 },
        { version: 2, accuracy: 0.84, grade: null },
      ]}
    />,
  );

  expect(screen.getByRole("img", { name: /accuracy and grade/ })).toBeDefined();
  expect(container.querySelectorAll(".mark-accuracy")).toHaveLength(2);
  expect(container.querySelectorAll(".mark-grade")).toHaveLength(1);
  const rows = screen.getAllByRole("row", { hidden: true }).slice(1);
  expect(rows.map((row) => row.textContent)).toEqual([
    "172.0%1.40",
    "284.0%Not graded",
  ]);
});

it("says when there is nothing to plot", () => {
  render(<VersionChart points={[]} />);

  expect(screen.getByText(/No version has been evaluated/)).toBeDefined();
});
