import { screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { setSignedIn } from "./testAuth";

vi.mock("./auth", () => import("./testAuth"));

it("renders the app into #root", async () => {
  setSignedIn(false);
  document.body.innerHTML = '<div id="root"></div>';

  await import("./main");

  expect(
    await screen.findByRole("heading", { name: "Sign in to UnderCover" }),
  ).toBeDefined();
});
