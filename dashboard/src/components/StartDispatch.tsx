import { useState } from "react";
import { startDispatch } from "../api";

const DEFAULT_CONCURRENCY = 3;
const MAX_CONCURRENCY = 25;

/** Choose how many claim agents work at once, and start a dispatch. */
export function StartDispatch({
  onStarted,
}: Readonly<{ onStarted: () => void }>) {
  const [concurrency, setConcurrency] = useState(DEFAULT_CONCURRENCY);
  const [message, setMessage] = useState("");

  const start = () => {
    setMessage("");
    startDispatch(concurrency)
      .then(onStarted)
      .catch((error: unknown) => {
        setMessage(error instanceof Error ? error.message : "Could not start.");
      });
  };

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        start();
      }}
    >
      <label>
        Claim agents at once{" "}
        <input
          type="number"
          min={1}
          max={MAX_CONCURRENCY}
          value={concurrency}
          onChange={(event) => {
            setConcurrency(Number(event.target.value));
          }}
        />
      </label>{" "}
      <button type="submit">Start a dispatch</button>
      {message && <p role="alert">{message}</p>}
    </form>
  );
}
