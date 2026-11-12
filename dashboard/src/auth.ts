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

/** Call back with whether a handler is signed in, now and on every change. */
export function onSignedIn(callback: (signedIn: boolean) => void): () => void {
  const { data } = supabase.auth.onAuthStateChange((_event, session) => {
    callback(session !== null);
  });
  return () => {
    data.subscription.unsubscribe();
  };
}
