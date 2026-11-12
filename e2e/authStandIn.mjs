// A stand-in for Supabase Auth on port 8004, so the end-to-end tests never reach
// the real project. It signs tokens with a key of its own, serves the public key
// at /auth/v1/.well-known/jwks.json, and answers the browser's cross-origin checks.
// Any of the three handlers signs in with the password "e2e-password".
import { createServer } from "node:http";
import { generateKeyPairSync, sign } from "node:crypto";

const PASSWORD = "e2e-password";
const HANDLERS = ["dana.whitfield", "marcus.oyelaran", "priya.raman"].map(
  (name) => `${name}@undercover.example`,
);

const { privateKey, publicKey } = generateKeyPairSync("ec", {
  namedCurve: "P-256",
});
const jwk = {
  ...publicKey.export({ format: "jwk" }),
  kid: "e2e",
  alg: "ES256",
};

const base64url = (value) => Buffer.from(value).toString("base64url");

function accessToken(email) {
  const header = base64url(
    JSON.stringify({ alg: "ES256", typ: "JWT", kid: "e2e" }),
  );
  const now = Math.floor(Date.now() / 1000);
  const payload = base64url(
    JSON.stringify({
      aud: "authenticated",
      role: "authenticated",
      sub: email,
      email,
      iat: now,
      exp: now + 3600,
    }),
  );
  const signature = sign("sha256", Buffer.from(`${header}.${payload}`), {
    key: privateKey,
    dsaEncoding: "ieee-p1363",
  });
  return `${header}.${payload}.${base64url(signature)}`;
}

function session(email) {
  return {
    access_token: accessToken(email),
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: `refresh-${email}`,
    user: {
      id: email,
      aud: "authenticated",
      email,
      app_metadata: {},
      user_metadata: {},
    },
  };
}

function reply(response, status, body) {
  response.statusCode = status;
  response.setHeader("content-type", "application/json");
  response.end(body === undefined ? undefined : JSON.stringify(body));
}

createServer((request, response) => {
  response.setHeader("access-control-allow-origin", "*");
  response.setHeader("access-control-allow-headers", "*");
  response.setHeader("access-control-allow-methods", "GET, POST, OPTIONS");
  const url = new URL(request.url ?? "/", "http://127.0.0.1:8004");
  if (request.method === "OPTIONS") return reply(response, 204);
  if (url.pathname === "/auth/v1/.well-known/jwks.json") {
    return reply(response, 200, { keys: [jwk] });
  }
  if (url.pathname === "/auth/v1/logout") return reply(response, 204);
  let text = "";
  request.on("data", (chunk) => (text += chunk));
  request.on("end", () => {
    const body = text ? JSON.parse(text) : {};
    if (url.searchParams.get("grant_type") === "refresh_token") {
      const email = String(body.refresh_token).replace("refresh-", "");
      return reply(response, 200, session(email));
    }
    if (HANDLERS.includes(body.email) && body.password === PASSWORD) {
      return reply(response, 200, session(body.email));
    }
    reply(response, 400, {
      code: 400,
      error_code: "invalid_credentials",
      msg: "Invalid login credentials",
    });
  });
}).listen(8004, "127.0.0.1");
