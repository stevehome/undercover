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
