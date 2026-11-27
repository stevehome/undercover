import { toWireAmount } from "./money";
import type { Appeal, Claim, Handler } from "./types";

export const dana: Handler = {
  handler_id: "HND-01",
  name: "Dana Whitfield",
  role: "Senior Claims Handler",
  email: "dana.whitfield@undercover.example",
  can_approve_over_limit: true,
};

export const marcus: Handler = {
  handler_id: "HND-02",
  name: "Marcus Oyelaran",
  role: "Claims Handler",
  email: "marcus.oyelaran@undercover.example",
  can_approve_over_limit: false,
};

/** An appeal still with the ombudsman, the way the dashboard reads it. */
export function appeal(more: Partial<Appeal> = {}): Appeal {
  return {
    claim_id: "CLM-1601",
    status: "with the ombudsman",
    label: "appeal open",
    ombudsman_reference: "OMB-2026-40117",
    received_on: "2026-10-06",
    recorded_by: "Marcus Oyelaran",
    recorded_on: "2026-10-06T09:00:00+00:00",
    decided_on: null,
    outcome_recorded_by: null,
    outcome_recorded_on: null,
    grounds: "The ferry was late and the hotel was lost.",
    ombudsman_reason: null,
    flagged: false,
    flag_reason: null,
    redress: null,
    redress_payment: null,
    claim: {
      summary: "Held overnight in Split",
      claim_type: "trip_delay",
      decision: "approve",
      payout: 37600,
      plan: "premium",
      customer: { customer_id: "CUS-3404", name: "Ivo Marin" },
    },
    ...more,
  };
}

/** An upheld appeal whose redress is waiting to be paid. */
export function upheld(more: Partial<Appeal> = {}): Appeal {
  return appeal({
    status: "upheld",
    label: "appeal upheld, redress waiting",
    decided_on: "2026-11-03",
    outcome_recorded_by: "Marcus Oyelaran",
    ombudsman_reason: "The wording was unclear about the hotel.",
    redress: {
      claim_amount: 14000,
      compensation: 7500,
      interest: 210,
      total: 21710,
    },
    ...more,
  });
}

/** An appeal as the API serves it: amounts as two-decimal strings. */
export function appealToWire(a: Appeal) {
  const wire = (cents: number) => toWireAmount(cents);
  return {
    ...a,
    redress: a.redress && {
      claim_amount: wire(a.redress.claim_amount),
      compensation: wire(a.redress.compensation),
      interest: wire(a.redress.interest),
      total: wire(a.redress.total),
    },
    redress_payment: a.redress_payment && {
      ...a.redress_payment,
      amount: wire(a.redress_payment.amount),
    },
    claim: {
      ...a.claim,
      payout: a.claim.payout === null ? null : wire(a.claim.payout),
    },
  };
}

/** A claim with a final decision: declined, so it can be appealed. */
export function decidedClaim(more: Partial<Claim> = {}): Claim {
  return {
    claim_id: "CLM-1601",
    policy_id: "POL-2404",
    customer_id: "CUS-3404",
    claim_type: "trip_delay",
    submitted_on: "2026-09-18",
    incident_date: "2026-09-13",
    incident_location: "Split, Croatia",
    summary: "Held overnight in Split",
    story: "The ferry left late.",
    items: [],
    amount_claimed: 66170,
    documents: [],
    status: "decided",
    decision: "decline",
    payout: 0,
    reason: "Not covered.",
    policy_reference: "Section 3",
    decided_on: "2026-09-22T10:00:00+00:00",
    decided_by: "Marcus Oyelaran",
    calculation: null,
    manual_version: "2026.2",
    over_approval_limit: 0,
    signed_off_by: null,
    signed_off_on: null,
    hold_reason: null,
    paid_amount: null,
    paid_on: null,
    evaluation_run_id: null,
    sent_back_decisions: [],
    policy: {
      policy_id: "POL-2404",
      customer_id: "CUS-3404",
      plan: "premium",
      add_ons: [],
      purchased_on: "2026-05-12",
      sold_through: "Direct",
      trip: {
        destination: "Split, Croatia",
        departs_on: "2026-09-10",
        returns_on: "2026-09-15",
      },
      travelers: ["Ivo Marin"],
      status: "active",
    },
    customer_previous_claims: [],
    ...more,
  };
}
