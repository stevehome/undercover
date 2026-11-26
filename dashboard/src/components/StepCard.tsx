import { useEffect, useState } from "react";
import type { CopilotStep } from "../types";
import { CardIcon } from "./CopilotIcons";

/** Text for a pane, or a word saying there is none. */
const shown = (text: string | null, none: string) =>
  text === null || text === "" ? none : text;

const SECOND_MS = 1000;
const TENTH = 10;

const seconds = (value: number) =>
  `${(Math.round(value * TENTH) / TENTH).toFixed(1)} s`;

/** The seconds a working step has run so far, counting up as the sidebar watches. */
function Elapsed({ startedOn }: Readonly<{ startedOn: string }>) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const tick = setInterval(() => {
      setNow(Date.now());
    }, SECOND_MS);
    return () => {
      clearInterval(tick);
    };
  }, []);
  return <>{seconds(Math.max(0, (now - Date.parse(startedOn)) / SECOND_MS))}</>;
}

function State({ step }: Readonly<{ step: CopilotStep }>) {
  if (step.state === "working") {
    return (
      <span className="step-state working">
        <span className="spinner" aria-hidden="true" />
        Working, <Elapsed startedOn={step.started_on} />
      </span>
    );
  }
  const took = step.seconds === null ? "" : `, ${seconds(step.seconds)}`;
  const label = { done: "Done", refused: "Refused", failed: "Failed" }[
    step.state
  ];
  return (
    <span className={`step-state ${step.state}`}>
      {label}
      {took}
    </span>
  );
}

/** One tool call of the Copilot: its kind, name and input, and how it is going.
 * Opened, it shows what was asked and what came back. An action stands out. */
export function StepCard({ step }: Readonly<{ step: CopilotStep }>) {
  const [open, setOpen] = useState(false);
  const files = Object.entries(step.files ?? {});
  return (
    <div className={`step-card ${step.kind === "action" ? "action" : ""}`}>
      <button
        type="button"
        className="step-head"
        aria-expanded={open}
        onClick={() => {
          setOpen(!open);
        }}
      >
        <CardIcon kind={step.kind} />
        <span className="mono step-name">{step.tool}</span>
        <span className="mono step-input">{step.input}</span>
        <State step={step} />
      </button>
      {step.reason !== null && <p className="step-reason">{step.reason}</p>}
      {open && (
        <div className="step-body">
          <h4>Asked</h4>
          <pre>{shown(step.input, "Nothing")}</pre>
          <h4>Came back</h4>
          <pre>{shown(step.result, "Nothing yet")}</pre>
          {files.length > 0 && (
            <ul className="step-files">
              {files.map(([file, source]) => (
                <li key={file}>
                  <span className="mono">{file}</span> from {source.system},
                  owned by {source.owner}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
