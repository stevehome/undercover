import type { CardKind } from "../types";

const PATHS: Record<CardKind, string> = {
  claims: "M6 3h9l4 4v14H6zM14 3v5h5M9 12h7M9 16h7",
  customers: "M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  context: "M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2zM8 7h7M8 11h7",
  "agent work":
    "M12 3v3M12 18v3M3 12h3M18 12h3M7 7l2 2M15 15l2 2M17 7l-2 2M9 15l-2 2",
  memory: "M7 3h10v18l-5-4-5 4z",
  action: "M13 2 5 14h6l-1 8 8-12h-6z",
};

/** A small icon for a kind of card; the kind's name is its label. */
export function CardIcon({ kind }: Readonly<{ kind: CardKind }>) {
  return (
    <svg
      className="card-icon"
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      role="img"
      aria-label={kind}
    >
      <path d={PATHS[kind]} />
    </svg>
  );
}

/** The Copilot's own mark: a speech bubble with a spark. */
export function CopilotMark() {
  return (
    <svg
      viewBox="0 0 24 24"
      width="20"
      height="20"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M4 5h16v11H9l-5 4zM12 8v5M9.5 10.5h5" />
    </svg>
  );
}

/** An arrow that points right to collapse the sidebar and left to open it. */
export function Chevron({ pointsRight }: Readonly<{ pointsRight: boolean }>) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="18"
      height="18"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={pointsRight ? "M9 5l7 7-7 7" : "M15 5l-7 7 7 7"} />
    </svg>
  );
}
