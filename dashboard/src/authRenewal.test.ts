import { afterEach, beforeEach, expect, it, vi } from "vitest";

const session = vi.hoisted(() => ({
  getSession: vi.fn(),
  refreshSession: vi.fn(() => Promise.resolve({})),
}));

vi.mock("@supabase/supabase-js", () => ({
  createClient: () => ({
    auth: {
      getSession: session.getSession,
      refreshSession: session.refreshSession,
    },
  }),
}));

import { RENEW_BELOW_SECONDS, renewSignIn } from "./auth";

const withSecondsLeft = (seconds: number) =>
  Promise.resolve({
    data: { session: { expires_at: Date.now() / 1000 + seconds } },
  });

beforeEach(() => {
  session.refreshSession.mockClear();
});

afterEach(() => {
  session.getSession.mockReset();
});

it("renews a sign-in with under twenty minutes left", async () => {
  session.getSession.mockReturnValue(withSecondsLeft(RENEW_BELOW_SECONDS - 60));

  await renewSignIn();

  expect(session.refreshSession).toHaveBeenCalledOnce();
});

it("leaves a sign-in with more than twenty minutes left", async () => {
  session.getSession.mockReturnValue(withSecondsLeft(RENEW_BELOW_SECONDS + 60));

  await renewSignIn();

  expect(session.refreshSession).not.toHaveBeenCalled();
});

it("does nothing when nobody is signed in", async () => {
  session.getSession.mockReturnValue(
    Promise.resolve({ data: { session: null } }),
  );

  await renewSignIn();

  expect(session.refreshSession).not.toHaveBeenCalled();
});
