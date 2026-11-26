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

async function startTurn(payload) {
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
