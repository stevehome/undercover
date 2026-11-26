/** Signing in: the one module that talks to Supabase Auth. */
import { createClient } from "@supabase/supabase-js";

const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_PUBLISHABLE_KEY,
);

/** Sign in with an email address and password; the error says what was wrong. */
export async function signIn(email: string, password: string): Promise<void> {
  const { error } = await supabase.auth.signInWithPassword({ email, password });
  if (error) throw new Error(error.message);
}

export async function signOut(): Promise<void> {
  await supabase.auth.signOut();
}

/** The session's access token, or null when nobody is signed in. */
export async function accessToken(): Promise<string | null> {
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
}

/** Seconds a sign-in may have left before it is renewed: the Copilot works with it. */
export const RENEW_BELOW_SECONDS = 20 * 60;

/** Renew the session when its sign-in has less than twenty minutes left. */
export async function renewSignIn(): Promise<void> {
  const { data } = await supabase.auth.getSession();
  const expires = data.session?.expires_at;
  if (
    expires !== undefined &&
    expires - Date.now() / 1000 < RENEW_BELOW_SECONDS
  ) {
    await supabase.auth.refreshSession();
  }
}

/** Call back with whether a handler is signed in, now and on every change. */
export function onSignedIn(callback: (signedIn: boolean) => void): () => void {
  const { data } = supabase.auth.onAuthStateChange((_event, session) => {
    callback(session !== null);
  });
  return () => {
    data.subscription.unsubscribe();
  };
}
