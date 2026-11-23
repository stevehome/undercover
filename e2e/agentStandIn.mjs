// A stand-in for the agent's AgentCore app on port 8003, so the end-to-end tests
// never reach the real one. It answers each payload posted to /invocations as taken
// and records it: GET /calls lists the operations and GET /bodies their other
// inputs, in the same order. GET /ping answers as the real app's does when idle.
import { createServer } from "node:http";

const calls = [];
const bodies = [];

createServer((request, response) => {
  response.setHeader("content-type", "application/json");
  if (request.method === "GET" && request.url === "/ping") {
    response.end(JSON.stringify({ status: "Healthy" }));
    return;
  }
  if (request.method === "GET" && request.url === "/calls") {
    response.end(JSON.stringify(calls));
    return;
  }
  if (request.method === "GET" && request.url === "/bodies") {
    response.end(JSON.stringify(bodies));
    return;
  }
  let text = "";
  request.on("data", (chunk) => (text += chunk));
  request.on("end", () => {
    const { operation, ...inputs } = text ? JSON.parse(text) : {};
    calls.push(operation);
    bodies.push(inputs);
    response.end(
      JSON.stringify({
        accepted: true,
        run_id: 1,
        round_id: 1,
        proposal_id: 1,
      }),
    );
  });
}).listen(8003, "127.0.0.1");
