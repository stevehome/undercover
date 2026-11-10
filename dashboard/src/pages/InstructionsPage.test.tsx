import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { InstructionsPage } from "./InstructionsPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the claim agent's instructions", async () => {
  const impl = (): Promise<Response> =>
    Promise.resolve(
      new Response(
        JSON.stringify({ instructions: "Call decide_claim exactly once." }),
      ),
    );
  vi.stubGlobal("fetch", vi.fn(impl));

  render(<InstructionsPage />);

  expect(
    await screen.findByText("Call decide_claim exactly once."),
  ).toBeDefined();
});
