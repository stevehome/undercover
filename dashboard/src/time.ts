/** Format a wire timestamp for people, in the viewer's own time zone. */
export function formatTime(iso: string): string {
  return new Date(iso).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

/** Format a length of time in milliseconds, such as "27.9 s" or "2 min 3 s". */
export function formatDuration(ms: number): string {
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.trunc(seconds / 60);
  return `${String(minutes)} min ${String(Math.round(seconds % 60))} s`;
}
