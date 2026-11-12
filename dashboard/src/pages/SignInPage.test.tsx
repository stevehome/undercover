import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { signIn } from "../testAuth";
import { SignInPage } from "./SignInPage";

vi.mock("../auth", () => import("../testAuth"));

afterEach(() => {
  cleanup();
  signIn.mockClear();
});

function fillAndSubmit() {
  fireEvent.change(screen.getByLabelText("Email address"), {
    target: { value: "dana.whitfield@undercover.example" },
  });
  fireEvent.change(screen.getByLabelText("Password"), {
    target: { value: "secret" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
}

it("signs in with the email address and password", () => {
  render(<SignInPage />);

  fillAndSubmit();

  expect(signIn).toHaveBeenCalledWith(
    "dana.whitfield@undercover.example",
    "secret",
  );
});

it("shows the reason when the sign-in is refused", async () => {
  signIn.mockRejectedValueOnce(new Error("Invalid login credentials"));
  render(<SignInPage />);

  fillAndSubmit();

  expect((await screen.findByRole("alert")).textContent).toBe(
    "Invalid login credentials",
  );
});
