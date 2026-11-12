import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { DiffView } from "./DiffView";

afterEach(cleanup);

it("marks additions and removals in color and in words", () => {
  const { container } = render(
    <DiffView
      lines={[
        { kind: "context", text: "keep" },
        { kind: "removed", text: "old" },
        { kind: "added", text: "new" },
      ]}
    />,
  );

  expect(container.querySelector(".diff-removed")?.textContent).toContain(
    "old",
  );
  expect(container.querySelector(".diff-added")?.textContent).toContain("new");
  expect(screen.getByText("Added:")).toBeDefined();
  expect(screen.getByText("Removed:")).toBeDefined();
});

it("says when nothing changed", () => {
  render(<DiffView lines={[]} />);

  expect(screen.getByText("Nothing changed.")).toBeDefined();
});
