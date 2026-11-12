import type { Round, Stage } from "../types";
import { StatusPill } from "./StatusPill";

const STEPS: { stage: Stage; label: string; counted?: boolean }[] = [
  { stage: "first evaluations", label: "First evaluations", counted: true },
  { stage: "improver working", label: "The improver is working" },
  { stage: "change waiting", label: "A change is waiting for approval" },
  { stage: "evaluations", label: "Evaluations", counted: true },
  { stage: "verdict", label: "Verdict" },
  { stage: "recipe waiting", label: "A recipe is waiting for approval" },
  { stage: "finished", label: "Finished" },
];

function stateOf(index: number, current: number, finished: boolean) {
  if (finished || index < current) return "done";
  return index === current ? "current" : "to-do";
}

/** Where a round has got to: the steps done, the one it is on and what is to come. */
export function RoundProgress({ round }: Readonly<{ round: Round }>) {
  const current = STEPS.findIndex((step) => step.stage === round.stage);
  const finished = round.stage === "finished";

  return (
    <div>
      <ol className="progress" aria-label={`Round ${String(round.round_id)}`}>
        {STEPS.map((step, index) => {
          const state = stateOf(index, current, finished);
          return (
            <li
              key={step.stage}
              className={`step step-${state}`}
              aria-current={state === "current" ? "step" : undefined}
            >
              {step.label}
              {step.counted && state === "current"
                ? `, ${String(round.progress)} of 3`
                : ""}
            </li>
          );
        })}
      </ol>
      {round.stage === "stopped" && <StatusPill status="stopped" />}
    </div>
  );
}
