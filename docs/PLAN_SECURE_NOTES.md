# Notes on the secure build

Notes from running and testing the build of `docs/PLAN_SECURE.md`. They are for the student; the product's own documents are `SPEC.md`, `TECH_STACK.md` and `STATUS.md`.

## How to test

**Automated, with no `.env` and no spend:**

```
npm run check
```

It runs lint, types, the Python tests, the dashboard tests, `check:server`, `npm run build` and the end-to-end tests.

**By hand, with `npm run dev` running and a seeded database:**

- The API key:
  - `curl -i http://127.0.0.1:8000/api/claims` gives 401.
  - `curl http://127.0.0.1:8000/api/health` gives 200.
  - `curl -H "X-API-Key: <your UNDERCOVER_API_KEY>" http://127.0.0.1:8000/api/claims` gives 200.
  - A header takes a colon, not an equals sign: `X-API-Key=...` sends no key, and the answer is `Sign in to do this`.
- The hidden-instruction check: `uv run -m agent CLM-1901` is referred, and the claim page shows the check's reason in its steps and decision. `uv run -m agent CLM-1001` starts with "Security check: no instructions found".
- Payment and sign-off: sign off a claim that is waiting for sign-off. It shows "Paid $X", with the handler's name and the time. A dispatch from the queue makes more claims wait.
- Lambda mode: see below.

The real-model runs cost a little: about $0.03 for the live checks of Phase 5. `npm run seed`, with `npm run dev` stopped, puts the database back to 26 waiting claims.

## Lambda mode on your Mac

`DATABASE_URL` is already in `.env`, on Supabase's session pooler (port 5432). For Lambda mode the port is 6543, the transaction pooler. Stop `npm run dev` first (both want port 8000), then run `npm run build` once and:

```
set -a; source .env; set +a
export DATABASE_URL="${DATABASE_URL/:5432\//:6543/}"
export AWS_LAMBDA_FUNCTION_NAME=lab
uv run -m uvicorn backend.main:app --port 8000
```

- `echo "$DATABASE_URL" | grep -o ':[0-9]*/postgres'` prints `:6543/postgres` and keeps the password out of the terminal.
- The exports last for that terminal window only. `.env` is not changed.
- Open `http://127.0.0.1:8000`: the backend serves the built dashboard. The dashboard's origin is different from `npm run dev`'s (:5173), so sign in again.

## Does the dashboard on AWS show the same data?

Yes, when the Lambda's `DATABASE_URL` is the same Supabase project. The data is in Supabase, not in either backend, so a sign-off or a decision made on one side shows on the other, and a reseed wipes it for both. A different project or schema shows different data, and a fresh project needs `npm run seed` first, because Lambda skips the schema and the seeding.

Reading and signing off need only the backend and the database. Starting a dispatch, an evaluation or an improvement round makes the backend call the agent's service, and nothing in this build puts that on AWS, so those buttons would fail unless the Lambda backend can reach a running service. The Lambda needs `DATABASE_URL`, `UNDERCOVER_API_KEY` and the Supabase URL and key; nothing has been deployed.

## What Azure is

We don't use Azure ourselves. The claim agent, the improver and the hidden-instruction check all call OpenRouter, which forwards each request to a company that hosts the model. The 502 errors named Azure as the provider for `openai/gpt-6-luna`. Every call carries `{"data_collection": "deny", "zdr": True}`, so OpenRouter may use only providers that keep no data, which narrows the choice and may leave no fallback. The 502 message ("high demand... exceeds the maximum usage size allowed during peak load") is Azure's capacity limit. The dispatcher retries a claim once and then leaves it for a handler; a new dispatch works it. OpenRouter's Activity page shows which provider served each request.

## Found in the live checks

- `openrouter/free` has no endpoint under the zero-retention setting: the check fails with a 404. The live checks ran on the configured models.
- About 6 of 40 reads signed in as Dana by script, each with a fresh token, got 401 "Your sign-in isn't valid". The cause: this Mac's clock runs a little behind Supabase's, so a fresh token's `iat` was ahead of it in 5 of 25 sign-ins (by 0.05 to 0.18 s), and PyJWT refuses such a token as not yet valid. Fixed with 10 s of leeway in `backend/auth.py`. A real handler could have met it too, as a failed first load right after signing in.
- Supabase rate-limits password sign-ins (429 `over_request_rate_limit`) when a script signs in too often. That is a limit of the scripts, not of the product.
- The dashboard's "Payment in progress" state can no longer be reached, because a sign-off pays in the one request.
- The Mangum deprecation warning in pytest comes from a third-party library.
- `/docs` and `/openapi.json` are still open.
- Supabase's transaction pooler accepts the engine's `search_path` option, so the tables need no schema qualifier.
