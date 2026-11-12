/** A stand-in for `auth.ts` in unit tests: a sign-in the test can flip. */
import { vi } from "vitest";

let signedIn = true;
const listeners = new Set<(signedIn: boolean) => void>();

export function setSignedIn(value: boolean) {
  signedIn = value;
  listeners.forEach((listener) => {
    listener(value);
  });
}

export const onSignedIn = (callback: (signedIn: boolean) => void) => {
  listeners.add(callback);
  callback(signedIn);
  return () => {
    listeners.delete(callback);
  };
};

export const signIn = vi.fn<(email: string, password: string) => Promise<void>>(
  () => Promise.resolve(),
);

export const signOut = vi.fn(() => {
  setSignedIn(false);
  return Promise.resolve();
});

export const accessToken = vi.fn(() => Promise.resolve("test-token"));
