import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, expect, it, vi } from "vitest";
import { wireEvaluation } from "../testHelpers";
import { EvaluationPage } from "./EvaluationPage";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows each claim with the handler's answer beside the agent's, and the misses", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(wireEvaluation)))),
  );

  render(
    <MemoryRouter initialEntries={["/evaluations/7"]}>
      <Routes>
        <Route path="/evaluations/:runId" element={<EvaluationPage />} />
      </Routes>
    </MemoryRouter>,
  );

  const hit = (await screen.findByText("CLM-1101")).closest("tr");
  const miss = screen.getByText("CLM-1102").closest("tr");
  expect(hit?.className).toBe("");
  expect(hit?.textContent).toContain("approve, $580.00approve, $580.00Right");
  expect(miss?.className).toBe("miss");
  expect(miss?.textContent).toContain("approve, $250.00decline");
  expect(miss?.textContent).toContain("Miss$1,500.00");
  expect(
    screen.getByRole("link", { name: "CLM-1102" }).getAttribute("href"),
  ).toBe("/claims/EVAL-7-CLM-1102");
});
