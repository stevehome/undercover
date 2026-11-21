import type { FileSource, Step } from "../types";

interface Used {
  source: FileSource;
  looked: string[];
}

/** What each file of the context layer was asked, once each, with the file's source. */
function byFile(steps: Step[]): Map<string, Used> {
  const used = new Map<string, Used>();
  for (const step of steps) {
    if (step.kind !== "lookup") continue;
    for (const [file, source] of Object.entries(step.files)) {
      const entry = used.get(file) ?? { source, looked: [] };
      if (!entry.looked.includes(step.text)) entry.looked.push(step.text);
      used.set(file, entry);
    }
  }
  return used;
}

/** Everything the agent looked up in the context layer, grouped by file. */
export function ContextUsed({ steps }: Readonly<{ steps: Step[] }>) {
  const used = byFile(steps);
  if (used.size === 0) return null;
  return (
    <>
      <h2>Context used</h2>
      {[...used].map(([file, { source, looked }]) => (
        <section key={file} className="context-file">
          <h3 className="mono">{file}</h3>
          <p className="from">
            {source.system}, owned by {source.owner}, last reviewed{" "}
            {source.reviewed}
          </p>
          <ul>
            {looked.map((text) => (
              <li key={text}>{text}</li>
            ))}
          </ul>
        </section>
      ))}
    </>
  );
}
