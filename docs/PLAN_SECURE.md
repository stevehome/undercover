# Plan: secure UnderCover and get it ready for AWS

Builds the four changes in `docs/SECURE.md`, one phase each: an API key for the agent, a check for instructions hidden in a claim, the agent's own API with a sign-off that pays, and a package ready for Lambda. A fifth phase holds the live checks and the last of the documents. Nothing here touches AWS.

SIDENOTE: For consistency with the course, please read `labs/week3day2_lab1.ipynb` and build the check in step 2 in the same style as the lab, and read `labs/week3day2_lab2.ipynb`, which deploys the app, without running it. Where the lab and this document differ, follow this document. Include this sidenote in your plan too.

I have read both labs. Lab 1 gives the check's shape: the security team's `SCREEN_INSTRUCTIONS`, a `Screening` model with `reason` first and then `instructions_found`, Structured Outputs, Luna at reasoning effort `none`, and a screen of the claim as the claim agent would read it. The claim agent here is a hand-written graph, not `create_agent`, so the lab's `before_agent` middleware becomes the graph's first node. Lab 2 gives the package's shape: `npm run build`, `uv export --only-group server`, Linux wheels with `uv pip install --python-platform x86_64-manylinux2014 --python-version 3.12 --only-binary :all:`, then `backend/`, `data/` and `dashboard/dist/`, with the handler `backend.main.handler` and the three environment variables.

## Where the build differs from the brief's notes

The brief's notes come from Ed's build, and ours took a different path in places. I follow the intent. These are the places, so you can correct me before I build.

- **The agent's operations.** The brief names eight: `get_claim`, `get_policy`, `get_claim_history`, `search_documents`, `read_section`, `calculate_payout`, `record_decision` and `pay_claim`. Our claim agent has six, with these `operation_id`s: `get_claim` (which already holds the policy and the claim history), `list_sections`, `get_section`, `calculate_payout`, `decide_claim` and `pay_claim`. Step 3 says each operation keeps its `operation_id`, so the document will hold our six and not rename anything. Phase 3 says what I'd leave out; tell me if you want the other names.
- **The agent's client.** The agent's requests go through `agent/backend_http.py`, not `agent/connection.py`. One request, `acquire_lease` in `agent/api.py`, bypasses `call` and uses the client directly, so the header must go in a shared function that both use.
- **Seeding.** There is no startup hook in `backend/main.py`. The database is created and seeded the first time `db.engine()` is used, in `backend/db.py`'s `_prepare`. On Lambda that must not run, since step 4 says nothing seeds there.
- **The sign-off.** `sign_off` puts the claim back in progress and the backend asks the agent's service to resume it, which pays it. The service's `resume_claim` has no check of its own. The payment is the graph's `pay` node.
- **The build.** `dashboard/vite.config.ts` has `envDir` as `".."` in every mode except `test`, so `vite build` should already read the root `.env`. Phase 4 proves it rather than assuming it.
- **The end-to-end tests** use Playwright's `request` against the dashboard's proxy, with no `e2e/api.ts`. The agent's side is played inside the specs.

## Design

- **Three kinds of backend route.** A route is for the agent (the key), shared (the key or a signed-in handler), or for a handler (sign-in). A route is shared when both the dashboard (`dashboard/src/api.ts`) and the agent's clients (`agent/api.py`, `agent/improver_api.py`) call it, for the agent when only they do, and for a handler otherwise. `GET /api/health` is open. A test asks every route for its answer with no credentials and expects a 401 from all but health, so a route added later can't be left open.
- **The key is not a handler.** The key unlocks the agent's routes and the shared reads. It never satisfies a route that needs a handler. A handler's sign-in never unlocks an agent route.
- **The check is code, not configuration.** It lives in `agent/screening.py` with its instructions as a constant. It isn't in the versioned configuration, and the improver has no tool that reaches it.
- **One `MODEL_NAME` read.** `harness.py` reads it twice today, for the claim agent and the improver. The check would make a third read, so the three share one helper.
- **The agent's API is generated, not written.** The document is built from the app's own routes, picked by `operation_id`, so it can't drift from the app.
- **A sign-off pays in the one statement that records it.** The payment can't be left half done, and the agent's service isn't needed.

## Phase 1: An API key for the agent

Adds `backend/api_key.py` (the check of the `X-API-Key` header, one job), `backend/access.py` (key or handler, for the shared reads) and the key in the agent's one HTTP function.

- `backend/api_key.py`: reads `UNDERCOVER_API_KEY` as each request arrives, compares with `secrets.compare_digest` on bytes, and raises `Unauthorized` for a missing, wrong or unset key. The header is hidden from the OpenAPI document (`include_in_schema=False`).
- `backend/auth.py`: the check of a token is split out so `access.py` can call it without needing Supabase for a request that carries the key.
- `backend/access.py`: the shared reads' rule. A valid key passes, and anything else needs a signed-in handler, so no key and no sign-in is a 401.
- `backend/main.py`: each route gets its kind, by the `dependencies=` argument or the handler's existing `SignedIn` / `Senior`. The routes are sorted by the rule above: agent routes include decisions, steps, payments, leases, model calls, work times, requeue, `/api/payouts`, documents, everything under `/api/runs` that the agent writes, everything under `/api/improver/`, and the configuration reads the agent makes. The shared reads include the claims, a claim's steps, a run, `/api/runs/current`, the models, the recipes and a round. Everything else the dashboard calls needs a handler, and those reads were open before, so this closes them. I check the table against both clients with a grep before I apply it.
- `agent/backend_http.py`: `send(method, path, **kwargs)` adds `X-API-Key` from the environment as each request is sent, so a command line that loads `.env` late, and tests that swap the client, both work. `call` and `acquire_lease` use it, so no request goes without. `require_key()` raises a clear error when the key is missing.
- `agent/service.py`: the startup calls `require_key()`, so the agent's service won't start without the key.
- `.env`: add `UNDERCOVER_API_KEY` from `secrets.token_urlsafe(32)` with a command that doesn't print it.
- `playwright.config.ts` gives the test backend a fixed key. `e2e/agentKey.ts` holds the matching header, and the specs that play the agent's side or read as one send it per call (not as a default for the whole context, which would hide a missing sign-in).
- Tests: `backend/tests/test_api_key.py`, `test_access.py`, `agent/tests/test_backend_http.py`; the existing backend tests set a key in `conftest.py`.
- `agent/tests/test_structure.py`: only `backend_http.py` names the header.
- Documents: `docs/SPEC.md` (the key, under Signing in), `docs/TECH_STACK.md` (replace "stay open until Week 3's API key"), `docs/STATUS.md`.

**Success criteria**

- [x] An agent route returns 401 with no key, 401 with a wrong key and succeeds with the right key (tests, for a read, a write and a payment).
- [x] A shared read returns 200 with the key, 200 with a handler's sign-in and 401 with neither.
- [x] A handler action (a sign-off, starting a dispatch, an evaluation or a round, a proposal's decision, a setting) returns 401 with only the key, and works with a handler.
- [x] With `UNDERCOVER_API_KEY` unset the backend starts, a handler can read the claims through the sign-in, and every agent route is refused with a 401.
- [x] The all-routes test finds every route but `GET /api/health` answering 401 to a request with no credentials, and health answering 200.
- [x] The agent's tests, with their test client swapped in, show the header on a call, on `acquire_lease` and on the improver's calls, read from the environment as sent.
- [x] The agent's service refuses to start with no key, and says `UNDERCOVER_API_KEY` is missing (test).
- [x] `npm run check` passes with `.env` moved out of the way, the end-to-end tests included.
- [x] `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the key. Commit.

## Phase 2: A check for instructions hidden in a claim

- `agent/screening.py`: the check. Holds the security team's instructions (the lab's `SCREEN_INSTRUCTIONS`, verbatim), the `Screening` model (`reason`, then `instructions_found`), and `screen(claim, claim_id, run_id)`, which asks the model with Structured Outputs and `include_raw=True`, records each model call and its cost through `api.record_model_call`, tries an answer that can't be read up to three times in all, and raises `ScreeningFailed` after the third. An error or a timeout isn't retried here and goes up. It reads the claim as `api.get_claim` returns it, which is how the claim agent reads it.
- `agent/harness.py`: `screening_model()`, GPT-6 Luna at effort `none`, or `MODEL_NAME` with no effort. `MODEL_NAME` is read in one helper that the claim agent, the improver and the check share. The provider rule for no training and no retention applies, as on the other models.
- `agent/claim_state.py` and `agent/claim_nodes.py`: a `flagged` field (the reason, or empty), a `screen` node (runs the check, records a first step such as "Security check: no instructions found" or the reason, and saves the result) and a `refer_flagged` node (records the referral with a payout of zero, the reason, and a policy reference of "Security check").
- `agent/claim_graph.py`: `START -> screen -> agent` when nothing is found, and `screen -> refer_flagged -> END` when something is. The graph takes the screening model beside the claim agent's, which is how tests give it a stub. `agent/agents.py` builds and passes it.
- Why a node, and two of them: a node saves when it finishes, so a restart or a sign-off carries on from saved progress and never runs the check again, while a claim started again on a new thread begins at `START` and is checked again. The referral is a node of its own so it can be repeated safely from the saved reason.
- Rate limits and timeouts from the check are let through as they are from the claim agent's model, so the dispatcher waits and carries on as for any other claim. Any other failure takes the existing path: the claim goes back in the queue, is tried once more, and is then left for a handler. The claim agent's model never sees the claim.
- `backend/seed_data.py`: seeding reads `data/security/claims.json`, `policies.json` and `customers.json` beside the queue's. `decisions.json` is never read, so CLM-1901 has no decision in the answer key and stays out of both evaluation sets. `data/claims.json` is untouched.
- `data/README.md`: CLM-1901 is in the queue now; its decision file is still unread. Tests that count 25 claims move to 26.

**Success criteria**

- [x] With a stub model that flags a claim: the claim is referred, with a payout of zero, the check's reason and "Security check" as its section, and the claim agent's stub model is never called (test).
- [x] With a stub that passes a claim: the claim agent works as before, and the first step is the check's result (test).
- [x] An unreadable answer is tried again and succeeds on the second try; three unreadable answers fail the claim and the claim agent's model is never called; an error from the check fails the claim the same way (tests).
- [x] Each attempt, retries included, is a model call recorded with its cost against the claim and its run, so the claim's cost on a run includes the check (test).
- [x] A claim carried on after a restart and a claim resumed after a sign-off don't run the check again; a claim on a new thread does (tests, with a counting stub).
- [x] CLM-1901 is in the queue with its policy and customer, `data/claims.json` is unchanged, and it is in neither evaluation set (tests).
- [x] The check's instructions and model are in no configuration version and no improver tool (a structure test: `screening.py` is the only module that holds them).
- [x] `MODEL_NAME` is read in one place in `agent/` (a structure test).
- [x] `npm run check` passes with `.env` moved out of the way. `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/STATUS.md` and `data/README.md` describe the check and CLM-1901. Commit.

## Phase 3: The agent's own API

- `backend/agent_api.py`: builds the document from the app's routes with FastAPI's `get_openapi`, keeping the routes whose `operation_id` is in `AGENT_OPERATIONS`. No `servers`. It takes the routes as an argument, so it never imports `main.py`.
- `backend/main.py`: `GET /api/agent/openapi.json` (`get_agent_openapi`, key or handler, one-line docstring).
- `AGENT_OPERATIONS`: `get_claim`, `list_sections`, `get_section`, `calculate_payout`, `decide_claim` and `pay_claim`. Left out on purpose: `record_step`, `record_model_call`, `record_work_segment`, the leases, `requeue_claim` and the runs, which are the agent's plumbing and not tools the model is given. The Gateway's Policy reads `amount` on `pay_claim`, so its input keeps that name.
- Checking the key adds no input to an operation, so the document has no key parameter. If the shared reads' bearer check shows in the document as a security scheme, `access.py` reads the header itself instead.
- `backend/payouts.py` and `backend/claims.py`: `pay` refuses any amount over the approval limit (read from the setting) with a 403 that names the limit, before it looks at the claim. A claim that was never approved gets the same answer.
- `backend/claims.py`: `sign_off` becomes one conditional update that records the handler and the time, the payment (the payout, to the cent, with the time) and the status `decided`, only on a claim waiting for sign-off. A second sign-off by the same handler returns the claim, and by another is a 409. An evaluation's claim still can't be signed off.
- `backend/agent_service.py` and the sign-off route: the sign-off no longer asks the agent's service to resume the claim, so `notify_sign_off` goes.
- `agent/claim_graph.py`: `approval` ends the graph, so an agent resumed after a sign-off records "Signed off by" and finishes without paying. The `pay` node is for an approval at or under the limit only.
- `agent/service.py`: `resume_claim` stays, since it finishes a paused claim's work and nothing in this change removes the agent's service. The backend no longer calls it.
- Tests: `test_agent_api.py` and the changed sign-off and payment tests in `backend/tests`, `agent/tests/test_claim_graph.py`.
- Documents: `docs/SPEC.md` (a sign-off pays; the in-progress state between sign-off and payment goes), `docs/TECH_STACK.md`, `docs/STATUS.md`. `e2e/claim.spec.ts` and `queue.spec.ts` follow the new sign-off and stop expecting a resume call.

**Success criteria**

- [x] The document's operations are exactly the six `operation_id`s above, it has no `servers` entry, no header or key parameter, and no security scheme (test).
- [x] Each operation keeps its `operation_id` and one-line description, and `pay_claim`'s input is `amount` (test).
- [x] The document returns 200 with the key, 200 with a handler and 401 with neither (test).
- [x] A payment of $1,000.01 on a claim that was never approved returns 403 naming the limit; one of exactly $1,000.00 on that claim gets the claim's own refusal; with the limit changed to $300, a $400 payment is refused (tests).
- [x] A sign-off pays the claim in the one request, records the handler and the time on both the sign-off and the payment, and leaves it `decided`; repeating it by the same handler pays nothing twice (tests).
- [x] An agent paused at its sign-off and resumed afterwards finishes without calling the payment operation (test with the client recording the paths it is asked for).
- [x] An under-the-limit approval is still paid by the agent, as before (test).
- [x] `npm run check` passes with `.env` moved out of the way. Documents updated. Commit.

## Phase 4: Ready for Lambda

- `package.json`: `build` runs `vite build dashboard` into `dashboard/dist`, and `check:server` runs `uv run --isolated --only-group server python -c "import backend.main"`, which leaves the project's `.venv` alone. `check` runs it.
- `dashboard/vite.config.ts`: kept as it is unless the build shows it doesn't read `.env` or reads one under test. The Supabase address and key come from `.env` when it exists and from the environment otherwise. If the build warns (a large chunk, for one), I split the dependencies into their own chunk and don't raise a limit.
- `backend/dashboard_files.py`: serves a built dashboard from a folder. Files at their own paths, any other path outside `/api/` gets `index.html`, and an unknown `/api/` path keeps its JSON 404.
- `backend/main.py`: mounts the build when `dashboard/dist` exists, and ends with `handler = Mangum(app, lifespan="off")`.
- `backend/db.py`: when `AWS_LAMBDA_FUNCTION_NAME` is set, the engine uses `NullPool` and `prepare_threshold=None`, and doesn't create the schema, create the tables or seed (the database is made and seeded from the laptop). Otherwise unchanged.
- `pyproject.toml`: the `server` group holds exactly what `backend` imports. The check finds what's missing.
- Anything the backend reads from the environment other than the three variables has a default or is read only by work that can't start on Lambda; I check by starting it with only `DATABASE_URL`, `VITE_SUPABASE_URL` and `UNDERCOVER_API_KEY`. It reads files only from the package and writes none (checked by a test that runs it with the package folder read-only).
- `docs/TECH_STACK.md`: a Deployment section naming the build command and its folder, what goes in the package, the Lambda handler, `backend.main:app` for a web server, and the environment variables. `docs/PROCESS.md` and `docs/STATUS.md`: the build and the server check.
- Tests: `backend/tests/test_dashboard_files.py`, `test_lambda.py`, and the engine test in `test_db.py`.

**Success criteria**

- [x] `npm run build` writes `dashboard/dist` and prints no warnings, with `.env` present, and with `.env` moved away and `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` in the environment, where the built files hold those values.
- [x] The Lambda handler, called with a Function URL event, answers `/api/health` with 200 (test); with a stand-in build, answers `/` and a dashboard page with `index.html`, a file at its own path, and an unknown `/api/` path with a JSON 404 (tests).
- [x] With no `dashboard/dist` the backend behaves as today, and `npm run dev` is unchanged (tests).
- [x] With `AWS_LAMBDA_FUNCTION_NAME` set the engine uses `NullPool`, `prepare_threshold=None`, and makes no schema, table or seed (test); without it the pool is as today.
- [x] `npm run check:server` passes, and fails if I add an import that the group lacks (tried once, then undone).
- [x] The backend starts with only the three variables set, and answers health, a claims read with the key, and a handler's read (tests, with a stand-in for sign-in).
- [x] The deployment package, built in a temporary folder the lab's way for Linux and Python 3.12, is under 50 MB zipped. I report its size. The build holds no tests and no `__pycache__`.
- [x] `npm run check` passes with `.env` moved out of the way, the server check included. Documents updated. Commit.

## Phase 5: Live checks and the last of the documents

Run after you reseed once. You stop `npm run dev` and run `npm run seed`, then start `npm run dev` again; I don't reseed.

**Success criteria**

- [ ] `curl` to an agent route (a decision on CLM-1001) without the key returns 401, and to `/api/health` returns 200.
- [ ] Dana Whitfield signs in on the dashboard (Playwright MCP, `HANDLER_PASSWORD` kept out of the transcript) and sees the queue as before, now 26 claims.
- [ ] `uv run -m agent CLM-1001` works the claim, with the check's result as its first step.
- [ ] A dispatch with 5 claim agents at once works the rest. CLM-1901 is referred with the check's reason, which the dashboard shows on the claim and in its steps; the other claims are decided as before.
- [ ] Dana signs off a held payout on the dashboard, and it is paid once, with her name and the time on the payment.
- [ ] An evaluation of the evaluation set's tiny five flags none of the claims.
- [ ] The backend started with `AWS_LAMBDA_FUNCTION_NAME` set and `DATABASE_URL` on port 6543 serves the claims to Dana, through the dashboard it serves at `http://127.0.0.1:8000` after `npm run build` (Playwright MCP); then the same with the variable unset. You stop `npm run dev` first, for port 8000.
- [ ] I report what the live runs spent, from the dashboard's totals (the claim's model cost, with the check's calls in it).
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/STATUS.md` and `data/README.md` describe the product as it now is.
- [ ] `npm run check` is green with `.env` moved out of the way, with the tests from every phase. A final review of the whole change against the checklist in `docs/CODE_STANDARDS.md`. Commit. I don't push.

## Things I'd like you to look at

- The six operations in Phase 3, against the brief's eight.
- Leaving `resume_claim` in the agent's service, though the backend stops calling it.
- Rate limits and timeouts from the check waiting and carrying on, as for the claim agent's model, in place of failing the claim.
- Skipping the schema and the seeding on Lambda. If Supabase's transaction pooler refuses the `search_path` option the engine passes, Phase 4's live check will show it, and the fix is to qualify the tables with the schema instead.
- The package takes `data/` whole, as the lab does, which includes `data/evals`, the answer key. Leaving that folder out of the package would be safer, and nothing on Lambda reads it.
