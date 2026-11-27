// A stand-in for the Copilot's AgentCore app on port 8007, so the end-to-end tests
// never reach the real one or a model. It answers each payload posted to /invocations
// as taken, then plays a scripted turn through our app on port 8010 with the
// handler's own sign-in, as the real Copilot does: a lookup, an action our app
// refuses, a pause for a confirmation, and after the handler's answer a sign-off or
// a cancel and a formatted answer. GET /payloads lists the payloads it was sent, with
// the sign-in left out.
import { createServer } from "node:http";

const APP = "http://127.0.0.1:8010";
const PAUSE_MS = 500;
const payloads = [];

const CARD = {
  kind: "sign_off",
  claim_id: "CLM-1003",
  customer: { customer_id: "CUS-3003", name: "Ana Souza" },
  payout: "3750.00",
  reason: "Covered by section 3.",
};

const REDRESS_CLAIM = "CLM-1602";
const REDRESS_CARD = {
  kind: "redress",
  claim_id: REDRESS_CLAIM,
  customer: { customer_id: "CUS-3408", name: "Gareth Ollander" },
  redress: {
    claim_amount: "400.00",
    compensation: "150.00",
    interest: "6.40",
    total: "556.40",
  },
  reason: "The wording was unclear about when the cover began.",
};

const ANSWER = [
  "I signed off **CLM-1003** and paid it.",
  "",
  "| Claim | Paid |",
  "| --- | --- |",
  "| CLM-1003 | $3,750.00 |",
  "",
  "- Nothing else needs you",
].join("\n");

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

async function call(signIn, path, body) {
  const response = await fetch(`${APP}/api/copilot${path}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${signIn}`,
    },
    body: JSON.stringify(body),
  });
  return response.json();
}

async function step(payload, tool, kind, input, outcome) {
  const { conversation_id: id, sign_in: signIn } = payload;
  const { step_id: stepId } = await call(signIn, `/conversations/${id}/steps`, {
    tool,
    kind,
    input,
  });
  await sleep(PAUSE_MS);
  await call(signIn, `/steps/${stepId}/finish`, outcome);
}

const done = (result) => ({ state: "done", result, files: null, reason: null });
const refused = (reason) => ({
  state: "refused",
  result: "",
  files: null,
  reason,
});

async function startRedressTurn(payload) {
  const { conversation_id: id, sign_in: signIn } = payload;
  await step(
    payload,
    "get_appeal",
    "claims",
    `claim_id: ${REDRESS_CLAIM}`,
    done("An upheld appeal, redress waiting"),
  );
  await call(signIn, `/conversations/${id}/waiting`, { card: REDRESS_CARD });
}

async function answerRedress(payload) {
  const { conversation_id: id, sign_in: signIn } = payload;
  const confirmed = payload.confirmed;
  if (confirmed) {
    await fetch(`${APP}/api/claims/${REDRESS_CLAIM}/appeal/redress`, {
      method: "POST",
      headers: { Authorization: `Bearer ${signIn}` },
    });
  }
  await step(
    payload,
    "pay_redress",
    "action",
    `claim_id: ${REDRESS_CLAIM}`,
    confirmed
      ? done("Paid")
      : refused("The handler cancelled. Nothing was paid."),
  );
  await call(signIn, `/conversations/${id}/done`, {
    text: confirmed
      ? "I paid the redress on **CLM-1602**: $556.40."
      : "I haven't paid it. What would you like instead?",
    model_calls: 2,
    cost_nanos: 800000,
    work_ms: 1800,
  });
}

async function startTurn(payload) {
  if (/redress/i.test(payload.message)) return startRedressTurn(payload);
  const { conversation_id: id, sign_in: signIn } = payload;
  await step(payload, "list_claims", "claims", "", done("26 claims"));
  await step(
    payload,
    "start_dispatch",
    "action",
    "agents: 10",
    refused("A dispatch is already running"),
  );
  await call(signIn, `/conversations/${id}/waiting`, { card: CARD });
}

async function answerConfirmation(payload) {
  if (payload.card?.kind === "redress") return answerRedress(payload);
  const { conversation_id: id, sign_in: signIn } = payload;
  const confirmed = payload.confirmed;
  await step(
    payload,
    "sign_off_claim",
    "action",
    "claim_id: CLM-1003",
    confirmed
      ? done("Paid")
      : refused("The handler cancelled. Nothing was signed off."),
  );
  await call(signIn, `/conversations/${id}/done`, {
    text: confirmed
      ? ANSWER
      : "I haven't signed off. What would you like instead?",
    model_calls: 3,
    cost_nanos: 1200000,
    work_ms: 2400,
  });
}

createServer((request, response) => {
  response.setHeader("content-type", "application/json");
  if (request.method === "GET") {
    response.end(JSON.stringify(payloads));
    return;
  }
  let text = "";
  request.on("data", (chunk) => (text += chunk));
  request.on("end", () => {
    const payload = JSON.parse(text);
    payloads.push({ ...payload, sign_in: undefined });
    if (payload.operation === "health") {
      response.end(JSON.stringify({ healthy: true }));
      return;
    }
    response.end(JSON.stringify({ accepted: true }));
    const play =
      payload.operation === "start_turn" ? startTurn : answerConfirmation;
    play(payload).catch((error) => {
      console.error(error);
    });
  });
}).listen(8007, "127.0.0.1");
