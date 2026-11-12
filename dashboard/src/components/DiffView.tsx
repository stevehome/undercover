import type { DiffLine } from "../types";

const MARKS = { added: "+", removed: "−", context: " ", hunk: "" } as const;

/** Lines changed, with additions and removals in color and marked by a sign too. */
export function DiffView({ lines }: Readonly<{ lines: DiffLine[] }>) {
  if (lines.length === 0) return <p>Nothing changed.</p>;
  return (
    <pre className="diff" aria-label="What changed">
      {lines.map((line, index) => (
        // The diff is fixed text, so a line's place is its identity.
        <div key={index} className={`diff-${line.kind}`}>
          <span aria-hidden="true">{MARKS[line.kind]} </span>
          <span className="sr-only">
            {line.kind === "added" && "Added: "}
            {line.kind === "removed" && "Removed: "}
          </span>
          {line.text}
        </div>
      ))}
    </pre>
  );
}
