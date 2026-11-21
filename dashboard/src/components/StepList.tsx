import type { Step } from "../types";

function Items({ items, empty }: Readonly<{ items: string[]; empty: string }>) {
  if (items.length === 0) return <span className="from"> {empty}</span>;
  return (
    <ul className="step-items">
      {items.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function StepItem({ step }: Readonly<{ step: Step }>) {
  switch (step.kind) {
    case "tool_call":
      return (
        <li className="agent-step tool-call">
          <span className="mono">{step.text}</span>
        </li>
      );
    case "lookup":
      return (
        <li className="agent-step">
          <span>{step.text}</span>{" "}
          <span className="from">
            from{" "}
            {Object.keys(step.files).map((file, index) => (
              <span key={file}>
                {index > 0 && ", "}
                <span className="mono">{file}</span>
              </span>
            ))}
          </span>
        </li>
      );
    case "memory_search":
      return (
        <li className="agent-step">
          <span>{step.text}</span>
          <Items items={step.found} empty="Found nothing." />
        </li>
      );
    case "memory_save":
      return (
        <li className="agent-step">
          <span>{step.text}</span>
          <Items items={step.saved} empty="Nothing was saved." />
        </li>
      );
    case "refusal":
      return (
        <li className="agent-step refusal">
          <strong>Refused by {step.source}</strong> {step.detail}
        </li>
      );
    case "note":
      return <li className="agent-step">{step.text}</li>;
  }
}

/** Every step of the agent's work on a claim, in order, by what kind of step it is. */
export function StepList({ steps }: Readonly<{ steps: Step[] }>) {
  if (steps.length === 0) return null;
  return (
    <>
      <h2>What the agent did</h2>
      <ol className="agent-steps">
        {steps.map((step) => (
          <StepItem
            key={`${step.recorded_on} ${step.kind} ${step.text}`}
            step={step}
          />
        ))}
      </ol>
    </>
  );
}
