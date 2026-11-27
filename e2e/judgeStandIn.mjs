// A stand-in for OpenRouter on port 8005, so the end-to-end tests never reach the
// real judge or the check of an appeal's text. Every explanation the judge is asked
// to grade gets a B (score 2.1), and both checks answer yes. GET /calls says how many
// times the judge was asked. A chat completion is the check of an appeal's text: it
// finds an instruction when the text says to ignore the rules or approve in full.
// GET /checks says how many times it was asked.
import { createServer } from "node:http";

let calls = 0;
let checks = 0;

const INSTRUCTION = /ignore your rules|approve in full/i;

function checkAnswer(text) {
  const found = INSTRUCTION.test(text);
  const finding = {
    reason: found
      ? "It tells the assistant to approve in full."
      : "The text only says what happened.",
    instructions_found: found,
  };
  return {
    id: "check",
    object: "chat.completion",
    created: 0,
    model: "stand-in",
    system_fingerprint: null,
    choices: [
      {
        index: 0,
        finish_reason: "stop",
        message: { role: "assistant", content: JSON.stringify(finding) },
      },
    ],
    usage: {
      prompt_tokens: 50,
      completion_tokens: 10,
      total_tokens: 60,
      cost: 0.00002,
    },
  };
}

const answer = {
  answers: {
    grade: {
      type: "score",
      score: 2.1,
      probabilities: { 0: 0.05, 1: 0.1, 2: 0.7, 3: 0.15 },
    },
    same_grounds: { type: "noul", noul: 0.9 },
    same_section: { type: "noul", noul: 0.8 },
  },
  model: "typesafe/jev-1.13",
  usage: { input_tokens: 100, output_tokens: 1, cost: 0.00004 },
};

createServer((request, response) => {
  response.setHeader("content-type", "application/json");
  if (request.method === "GET" && request.url === "/calls") {
    response.end(JSON.stringify(calls));
    return;
  }
  if (request.method === "GET" && request.url === "/checks") {
    response.end(JSON.stringify(checks));
    return;
  }
  let text = "";
  request.on("data", (chunk) => (text += chunk));
  request.on("end", () => {
    if (request.url.includes("chat/completions")) {
      checks += 1;
      response.end(JSON.stringify(checkAnswer(text)));
      return;
    }
    calls += 1;
    response.end(JSON.stringify(answer));
  });
}).listen(8005, "127.0.0.1");
