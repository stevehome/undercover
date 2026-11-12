export type ClaimStatus =
  "waiting" | "in progress" | "waiting for sign-off" | "decided";

export type Decision = "approve" | "decline" | "refer";

/** Amounts are whole cents. */
export interface ClaimSummary {
  claim_id: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  status: ClaimStatus;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface Document {
  name: string;
  type: string;
  content: string;
}

export interface Policy {
  policy_id: string;
  customer_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  sold_through: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
  };
  travelers: string[];
  status: string;
}

export interface PreviousClaim {
  claim_id: string;
  filed_on: string;
  incident_date: string;
  claim_type: string;
  summary: string;
  outcome: string;
}

export interface Claim {
  claim_id: string;
  policy_id: string;
  customer_id: string;
  claim_type: string;
  submitted_on: string;
  incident_date: string;
  incident_location: string;
  summary: string;
  story: string;
  items: Item[];
  amount_claimed: number;
  documents: Document[];
  status: ClaimStatus;
  decision: Decision | null;
  payout: number | null;
  reason: string | null;
  policy_reference: string | null;
  decided_on: string | null;
  over_approval_limit: number | null;
  signed_off_by: string | null;
  signed_off_on: string | null;
  paid_amount: number | null;
  paid_on: string | null;
  /** The evaluation this claim is a copy for, or null for a queue claim. */
  evaluation_run_id: number | null;
  policy: Policy;
  customer_previous_claims: PreviousClaim[];
}

export interface Step {
  recorded_on: string;
  text: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  email: string;
  can_approve_over_limit: boolean;
}

export type RunClaimStatus =
  "to do" | "in progress" | "done" | "left for a handler" | "still in progress";

export interface RunClaim {
  claim_id: string;
  status: RunClaimStatus;
  attempts: number;
  note: string | null;
}

export interface RunSummary {
  approved: number;
  declined: number;
  referred: number;
  waiting_for_sign_off: { claim_id: string; payout: number }[];
  left_for_a_handler: string[];
  still_in_progress: string[];
}

export interface Run {
  run_id: number;
  kind: "dispatch" | "evaluation";
  status: "running" | "finished" | "stopped";
  concurrency: number;
  model: string;
  reasoning_effort: string;
  started_on: string;
  finished_on: string | null;
  claims: RunClaim[];
  model_calls: number;
  total_tokens: number;
  /** Model cost in whole billionths of a dollar. */
  cost_nanos: number;
  work_ms: number;
  summary: RunSummary;
}

export type EvalSet = "evaluation" | "held_out";

export interface Measures {
  /** Shares are from 0 to 1. */
  decision_accuracy: number;
  accuracy: number;
  straight_through: number;
  /** Whole cents. */
  cost_of_mistakes: number;
  /** Whole billionths of a dollar. */
  model_cost_per_claim_nanos: number;
  seconds_per_claim: number;
  run_seconds: number | null;
  /** The judge's average grade from 0 to 3; null when no claim was graded. */
  grade: number | null;
  /** The judge's cost, in whole billionths of a dollar. */
  judge_cost_nanos: number;
}

export interface ClaimGrade {
  score: number;
  letter: "A" | "B" | "C" | "F";
  /** The two checks as probabilities from 0 to 1, and whether each matched. */
  same_grounds: number;
  same_section: number;
  same_grounds_matched: boolean;
  same_section_matched: boolean;
}

export interface EvaluationClaim {
  claim_id: string;
  source_claim_id: string;
  status: RunClaimStatus;
  note: string | null;
  handler_decision: Decision;
  handler_payout: number;
  agent_decision: Decision | null;
  agent_payout: number | null;
  reason: string | null;
  right: boolean;
  mistake_cost: number;
  cost_nanos: number;
  work_ms: number;
  /** The judge's grade of the agent's explanation; null when not graded. */
  grade: ClaimGrade | null;
  judge_cost_nanos: number;
}

export interface Evaluation {
  run_id: number;
  status: "running" | "finished" | "stopped";
  eval_set: EvalSet;
  tiny: boolean;
  /** The round that started this evaluation; null for one started by hand. */
  round_id: number | null;
  concurrency: number;
  model: string;
  reasoning_effort: string;
  started_on: string;
  finished_on: string | null;
  measures: Measures;
  claims: EvaluationClaim[];
}

export interface Setting {
  key: string;
  label: string;
  group: string;
  unit: string;
  value: string;
  maximum: string;
  changed_by: string | null;
  changed_on: string | null;
}

export interface AllowedModel {
  model: string;
  reasoning_efforts: string[];
  input_price_per_million: number;
  output_price_per_million: number;
}

export type Verdict = "kept" | "rolled back";

/** Averages of a version's whole-set evaluations that rounds ran on it. */
export interface Scores {
  runs: number;
  /** A share from 0 to 1; null when there is no run. */
  accuracy: number | null;
  /** From 0 to 3; null when no claim was graded. */
  grade: number | null;
  /** Whole billionths of a dollar. */
  cost_per_claim_nanos: number | null;
  seconds_per_claim: number | null;
}

export interface Configuration {
  version: number;
  instructions: string;
  model: string;
  reasoning_effort: string;
  reason: string;
  proposed_by: string;
  approved_by: string | null;
  approved_on: string | null;
  round_id: number | null;
  verdict: Verdict | null;
  verdict_reason: string | null;
  created_on: string;
  held_out: Scores;
}

export interface Recipe {
  version: number;
  text: string;
  reason: string;
  proposed_by: string;
  approved_by: string | null;
  verdict: Verdict | null;
  created_on: string;
}

export interface DiffLine {
  kind: "added" | "removed" | "context" | "hunk";
  text: string;
}

export interface ConfigurationDiff {
  version: number;
  from_version: number | null;
  lines: DiffLine[];
  model_before: string | null;
  model_after: string;
  reasoning_effort_before: string | null;
  reasoning_effort_after: string;
}

export type Stage =
  | "first evaluations"
  | "improver working"
  | "change waiting"
  | "evaluations"
  | "verdict"
  | "recipe waiting"
  | "finished"
  | "stopped";

export type ProposalStatus = "pending" | "approved" | "rejected";

export interface Proposal {
  proposal_id: number;
  round_id: number;
  kind: "change" | "recipe";
  status: ProposalStatus;
  reason: string;
  created_on: string;
  decided_by: string | null;
  decided_on: string | null;
  rejection_reason: string | null;
  version: number | null;
  from_version: number;
  lines: DiffLine[];
  /** Only a change has the model and effort before and after. */
  model_before?: string;
  model_after?: string;
  reasoning_effort_before?: string;
  reasoning_effort_after?: string;
}

export interface Round {
  round_id: number;
  stage: Stage;
  /** 1, 2 or 3 of 3 in the stages that count evaluations. */
  progress: number;
  recipe_version: number;
  settings: Record<string, string>;
  started_by_name: string;
  started_on: string;
  finished_on: string | null;
  configuration_version: number | null;
  improver_reason: string | null;
  held_out_before: Scores | null;
  held_out_after: Scores | null;
  verdict: Verdict | null;
  verdict_reason: string | null;
  /** Whole billionths of a dollar. */
  cost_nanos: number;
  /** Whole cents. */
  spending_limit: number;
  proposals: Proposal[];
}
