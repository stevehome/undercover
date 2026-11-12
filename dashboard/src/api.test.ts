import { afterEach, expect, it, vi } from "vitest";
import { fetchClaim, fetchClaims, startDispatch } from "./api";
import { accessToken, signOut } from "./testAuth";

vi.mock("./auth", () => import("./testAuth"));

afterEach(() => {
  vi.unstubAllGlobals();
});

it("rejects instead of returning an error body as data", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(new Response('{"detail":"No claim"}', { status: 404 })),
    ),
  );

  await expect(fetchClaim("CLM-9999")).rejects.toThrow("404");
});

it("reads wire amounts as whole cents", async () => {
  const summary = { claim_id: "CLM-1001", amount_claimed: "1234.50" };
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify([summary])))),
  );

  const [claim] = await fetchClaims();

  expect(claim.amount_claimed).toBe(123450);
});

it("sends the signed-in handler's token with an action", async () => {
  const fetchMock = vi.fn(() =>
    Promise.resolve(new Response('{"run_id":1}', { status: 202 })),
  );
  vi.stubGlobal("fetch", fetchMock);

  await startDispatch(3);

  const [, init] = (
    fetchMock.mock.calls as unknown as [string, RequestInit][]
  )[0];
  expect(new Headers(init.headers).get("Authorization")).toBe(
    "Bearer test-token",
  );
});

it("sends no token when nobody is signed in", async () => {
  accessToken.mockResolvedValueOnce(null as unknown as string);
  const fetchMock = vi.fn(() => Promise.resolve(new Response("[]")));
  vi.stubGlobal("fetch", fetchMock);

  await fetchClaims();

  const [, init] = (
    fetchMock.mock.calls as unknown as [string, RequestInit][]
  )[0];
  expect(new Headers(init.headers).has("Authorization")).toBe(false);
});

it("signs the handler out when the backend refuses their token", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(new Response('{"detail":"Sign in"}', { status: 401 })),
    ),
  );

  await expect(startDispatch(3)).rejects.toThrow("Sign in");

  expect(signOut).toHaveBeenCalled();
});
