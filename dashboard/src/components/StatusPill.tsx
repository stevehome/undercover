const TONES: Record<string, string> = {
  // A claim, a run's claim, a proposal, a verdict or a round: the same words in the
  // same colors everywhere.
  waiting: "info",
  "to do": "info",
  decided: "good",
  done: "good",
  Right: "good",
  Miss: "bad",
  kept: "good",
  finished: "good",
  approved: "good",
  "in progress": "wait",
  pending: "wait",
  "change waiting": "wait",
  "recipe waiting": "wait",
  "waiting for sign-off": "alert",
  "still in progress": "alert",
  "rolled back": "bad",
  stopped: "bad",
  rejected: "bad",
  "left for a handler": "bad",
};

/** A status as a word in a color, so color is never the only signal. */
export function StatusPill({ status }: Readonly<{ status: string }>) {
  return (
    <span className={`pill pill-${TONES[status] ?? "info"}`}>{status}</span>
  );
}
