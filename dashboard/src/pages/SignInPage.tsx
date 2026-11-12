import { useState } from "react";
import type { SyntheticEvent } from "react";
import { signIn } from "../auth";
import { PageHeader } from "../components/PageHeader";

export function SignInPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    setError(null);
    signIn(email, password).catch((failure: unknown) => {
      setError(failure instanceof Error ? failure.message : "Sign-in failed");
    });
  };

  return (
    <main className="panel sign-in">
      <PageHeader title="Sign in to UnderCover">
        Use your email address and password. There is no sign-up: ask your team
        lead.
      </PageHeader>
      <form onSubmit={submit}>
        <label>
          Email address
          <input
            type="email"
            autoComplete="username"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
            }}
            required
          />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => {
              setPassword(event.target.value);
            }}
            required
          />
        </label>
        {error && <p role="alert">{error}</p>}
        <button type="submit">Sign in</button>
      </form>
    </main>
  );
}
