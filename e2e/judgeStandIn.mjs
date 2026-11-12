// A stand-in for OpenRouter's Decisions endpoint on port 8005, so the end-to-end
// tests never reach the real judge. Every explanation gets a B (score 2.1), and
// both checks answer yes. GET /calls says how many times it was asked.
import { createServer } from "node:http";

let calls = 0;

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
  request.resume();
  request.on("end", () => {
    calls += 1;
    response.end(JSON.stringify(answer));
  });
}).listen(8005, "127.0.0.1");
