import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { StatusPill } from "./StatusPill";

afterEach(cleanup);

it.each([
  ["kept", "pill-good"],
  ["waiting for sign-off", "pill-alert"],
  ["rolled back", "pill-bad"],
  ["in progress", "pill-wait"],
  ["decided", "pill-good"],
  ["waiting", "pill-info"],
])("shows %s as a word in a color", (status, tone) => {
  render(<StatusPill status={status} />);

  expect(screen.getByText(status).className).toContain(tone);
});
