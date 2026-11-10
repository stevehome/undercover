// A stand-in for the agent's service on port 8003, so the end-to-end tests
// never reach the real one. It records every call and its body; GET /calls
// lists the paths and GET /bodies the bodies, in the same order.
import { createServer } from "node:http";

const calls = [];
const bodies = [];

createServer((request, response) => {
  response.setHeader("content-type", "application/json");
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
    calls.push(request.url);
    bodies.push(text ? JSON.parse(text) : null);
    response.statusCode = 202;
    response.end(JSON.stringify({ run_id: 1 }));
  });
}).listen(8003, "127.0.0.1");
