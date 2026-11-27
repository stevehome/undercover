import type {
  CardKind,
  Conversation,
  CopilotStep,
  Handler,
  SignOffCard,
  StepState,
} from "./types";

export const dana: Handler = {
  handler_id: "HND-01",
  name: "Dana Whitfield",
  role: "Senior Claims Handler",
  email: "dana.whitfield@undercover.example",
  can_approve_over_limit: true,
};

export function step(
  state: StepState = "done",
  kind: CardKind = "claims",
  more: Partial<CopilotStep> = {},
): CopilotStep {
  return {
    id: 1,
    message_id: 1,
    tool: "get_claim",
    kind,
    input: "claim_id: CLM-1012",
    state,
    started_on: new Date().toISOString(),
    seconds: state === "working" ? null : 1.24,
    result: state === "working" ? null : "The claim came back",
    files: null,
    reason: null,
    ...more,
  };
}

export const card: SignOffCard = {
  kind: "sign_off",
  claim_id: "CLM-1003",
  customer: { customer_id: "CUS-3003", name: "Ana Souza" },
  payout: 375000,
  reason: "Covered by section 3.",
};

export function conversation(more: Partial<Conversation> = {}): Conversation {
  return {
    conversation_id: "copilot-1",
    title: "Who needs me?",
    status: "done",
    card: null,
    failure: null,
    messages: [
      {
        id: 1,
        role: "handler",
        text: "Who needs me?",
        created_on: "2026-01-01T00:00:00+00:00",
        model_calls: null,
        cost_nanos: null,
        seconds: null,
      },
      {
        id: 2,
        role: "copilot",
        text: "Claim CLM-1003 needs you.",
        created_on: "2026-01-01T00:00:05+00:00",
        model_calls: 2,
        cost_nanos: 624000,
        seconds: 2.5,
      },
    ],
    steps: [step()],
    ...more,
  };
}

/** A conversation as the API serves it: costs and payouts as strings, in dollars. */
export function conversationToWire(chat: Conversation) {
  return {
    ...chat,
    card: chat.card && { ...chat.card, payout: "3750.00" },
    messages: chat.messages.map(({ cost_nanos, ...message }) => ({
      ...message,
      cost: cost_nanos === null ? null : "0.000624000",
    })),
  };
}
