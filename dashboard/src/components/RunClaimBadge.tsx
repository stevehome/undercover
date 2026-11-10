import type { RunClaimStatus } from "../types";

const BACKGROUND: Record<RunClaimStatus, string> = {
  "to do": "var(--sea-green)",
  "in progress": "var(--marigold)",
  done: "var(--cerulean)",
  "left for a handler": "var(--raspberry)",
  "still in progress": "var(--coral)",
};

const INK: Record<RunClaimStatus, string> = {
  "to do": "var(--midnight)",
  "in progress": "var(--midnight)",
  done: "#ffffff",
  "left for a handler": "#ffffff",
  "still in progress": "var(--midnight)",
};

export function RunClaimBadge({
  status,
}: Readonly<{ status: RunClaimStatus }>) {
  return (
    <span
      className="status-badge"
      style={{ background: BACKGROUND[status], color: INK[status] }}
    >
      {status}
    </span>
  );
}
