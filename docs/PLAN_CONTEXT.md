# Plan: the context layer, memory and the Gateway for the claim agent

Builds the five steps in `docs/CONTEXT.md`, one phase each: the claim agent's tools from the Gateway, the context layer as its own service, a complete decision record, a memory of each customer, and every step on the claim page. A sixth phase holds the live checks and the last of the documents. Nothing here creates anything on AWS: the Gateway, the Lambda functions and the Memory are covered by stand-ins and tests, and your notebook creates the real ones later.

SIDENOTE: For consistency with the course, please read `labs/week3day3.ipynb`, which deploys the app and the context layer, creates the Gateway and the memory, and runs the agent against them, without running it. Where the notebook and this document differ, follow this document. Include this sidenote in your plan too.

I have read the notebook, and your `labs/week3day2_lab2_record_decision_steveh.ipynb` as the brief asks. From the notebook I take the shape of the deployment: the context layer on Lambda as `context.server.handler` behind a Function URL with IAM auth, a Gateway with two targets (`undercover-app` as an OpenAPI target with the API key, `undercover-context` as an MCP server target signed for `lambda`), a Cedar permit for each target beside the forbid on payments over $1,000, and the agent on the laptop with `UNDERCOVER_GATEWAY_URL` and `UNDERCOVER_MEMORY_ID` in `.env`. From yours I take the lessons that bite: the Gateway turns an input's `anyOf` and an enum into types a policy can't compare with a plain value, which is why `Amount` is a `number` and the decision a `string` in the agent's API document (`docs/TECH_STACK.md`), and the new operations must keep to that.

## Where the build differs from the brief's notes

The brief's notes come from Ed's build, and ours took a different path in places. I follow the intent. These are the places, so you can correct me before I build.

- **The agent's operations.** The brief ends with six: `get_claim`, `get_policy`, `get_claim_history`, `calculate_payout`, `record_decision` and `pay_claim`. Ours will have four, with these `operation_id`s: `get_claim` (which already holds the policy and the claim history, as your note in the brief says), `calculate_payout`, `decide_claim` and `pay_claim`. `list_sections` and `get_section` leave with the documents. Splitting `get_claim` in three would add two operations and change the check's read of the claim for no gain.
- **The documents.** The brief says the context layer's `search_documents` and `read_section` work "as the app's operations of the same names do today". Ours are `list_sections` (headings) and `get_section` (by heading), and the app has never had a search. So the context layer gets the two tools as the brief lists them, `search_documents(query)` and `read_section(document, number)`, and the search is new code. The sections come from the numbered headings, as in the notebook.
- **The instructions.** The brief says they still end with the contents of both documents. Ours don't: version 1 (`data/claim_instructions.md`) points the agent at the documents' tools. They stay goals that point at the tools, now the context layer's, and name the memory.
- **Our modules.** The documents are in `backend/reference.py` and `backend/seed_data.py` (no `documents.py`, `configuration.py` or `database.py`). The agent's tools are `agent/tools.py` on `agent/api.py`, with `ClaimContext` in `agent/contexts.py`, and the graph is `claim_graph.py` and `claim_nodes.py` (no `connection.py`, no `harness.py` graph). The dashboard's claim page is one file, with no `StepList`, `SectionsRead` or `DecisionPanel` to extend.
- **Steps have no kinds.** `claim_steps` holds only text, and the dashboard shows a list. Step 5's kinds (a tool call, a lookup, a memory search or save, a refusal) are new, in the backend, `agent/api.py` and `dashboard/src/api.ts`.
- **The calculation has no claim.** `calculate_payout` takes a `policy_id` from the model and keeps nothing. To keep the latest calculation for each claim's attempt, and to take no id from the model, it moves under the claim (`POST /api/claims/{claim_id}/payout`) and reads the policy from the claim. Its `operation_id` stays.
- **An approval that pays nothing** isn't refused today, though the brief lists that rule as unchanged. Step 3 adds it.
- **The record's field names.** The dictionary calls the section `section` and the time `decided_at`; ours are `policy_reference` and `decided_on`, which the dashboard and many tests use. I add `calculation`, `decided_by` and `manual_version` under the dictionary's names and keep ours.
- **The agent's address.** The notebook runs the agent with `UNDERCOVER_API` set to the app on Lambda; our agent reads `UNDERCOVER_BACKEND` (`agent/backend_http.py`). I keep ours, and your copy of the notebook needs that one word changed.
- **Seeding** is `seed_data.py`, which splits the documents at `## ` headings today. The app no longer needs sections, since its two document operations go, so it keeps each document's whole text and version.
- **Live runs.** The brief says the default model. `openrouter/free` has no endpoint under our zero-retention setting, so the live runs use the configured models.

## Design

- **Two routes, one set of tools.** The model's tools stay module-level in `agent/tools.py`. They take the route from `ClaimContext`, which the claim run builds, so a tool is never built per call. A route is `agent/gateway.py` (the Gateway's MCP tools, signed) or `agent/direct.py` (the app with the key, the context layer over unsigned MCP). `agent/routes.py` picks one when a claim graph is built, from `agent/endpoints.py`, which reads `UNDERCOVER_GATEWAY_URL`, `UNDERCOVER_CONTEXT` and `UNDERCOVER_MEMORY_ID` when asked, never at import.
- **One place calls MCP.** `agent/mcp_connection.py` calls one MCP endpoint from synchronous code, on an event loop of its own for each call that it closes without touching the thread's loop, so the main thread keeps the loop Mangum's tests need. Both routes use it. `agent/sigv4.py` signs for the Gateway.
- **The model's bookkeeping isn't the model's tools.** Steps, model calls, work times, leases, the check's read and referral and the runs go straight to the app with the key. Only the model's tools and the payment go through the Gateway, so the Policy covers both.
- **A refusal has three sources and one shape for the model.** The app (`ApiRefusal`), the context layer (a tool error) and the Gateway's Policy (`McpError`, "Tool Execution Denied", raised by the client, which the Gateway route turns into a `GatewayRefusal`). The tools node turns each into a refusal the model reads, and the step recorder records it with its source.
- **The context layer is a service, not a library.** `context/` holds the files data governance owns, which I don't change, and the code that serves them. It reads the files once when the process starts. It has its own dependency group and its own import check, like the app.
- **Memory is a node.** Saving runs in code after the decision is read back, so it happens once even when work carries on after a restart. A claim the check referred never reaches it, and an evaluation's claim graph is built without memory.
- **Steps record themselves.** A `wrap_tool_call` on the tools node, in `agent/step_recording.py`, records each call, lookup and refusal, so the tools don't each record a step.

## Phase 1: The claim agent's tools from the Gateway

Puts the app's tools on both routes. The context layer joins them in Phase 2.

- `agent/endpoints.py`, `agent/sigv4.py`, `agent/mcp_connection.py`, `agent/gateway.py`, `agent/direct.py`, `agent/routes.py`: as in the design. Each tool is named `<target>___<operation>` on the Gateway (`undercover-app` here).
- `agent/contexts.py`: `ClaimContext` gains the claim's policy and customer ids and its route, which `agents.py` fills from the claim when it builds the graph.
- `agent/tools.py`: `get_claim`, `calculate_payout` and `decide_claim` take no id from the model; they fill in the claim and its policy. Recording a decision still ends the work through the graph's state. The tools node handles refusals from every source.
- `agent/claim_nodes.py` and `claim_graph.py`: the `pay` node pays through the route. When the Gateway refuses the payment, the graph records the refusal and asks the app to hold the claim, so the claim waits for a sign-off.
- `backend/claims.py`, `backend/main.py`, `backend/tables.py`: `hold_for_sign_off` moves an approved, unpaid claim to waiting for sign-off, with a `hold_reason` of `gateway` that the claim carries; any other claim is a 409. Only the agent's key can call it, and it isn't in the agent's API document.
- `dashboard/src/components/PaymentPanel.tsx`: says the Gateway refused the payment when the reason is `gateway`, and says the payout is over the approval limit otherwise.
- `agent/tests/`: a stand-in Gateway (a real MCP server over streamable HTTP that names its tools as the Gateway does and refuses like its Policy) and its tests; the structure tests keep boto3 signing to `sigv4.py`, `langchain_mcp_adapters` to `mcp_connection.py`, and every outside call to `api.py`, `improver_api.py`, `gateway.py` and `direct.py`.

**Success criteria**

- [x] Through the stand-in Gateway, `get_claim`, `calculate_payout`, `decide_claim` and the payment arrive as `undercover-app___<operation>`, signed with SigV4 for `bedrock-agentcore` (a test reads the request's credential scope).
- [x] On the direct route the same tools have the same names and inputs, and none of them has a claim, policy or customer id among the model's inputs (a test over the tools' schemas).
- [x] A refusal by the app reaches the model as a refusal with its reason on each route, and never as a success.
- [x] A refusal by the Gateway's Policy on a tool is recorded on the claim as the Gateway's, and the model's next call goes ahead.
- [x] A payment the Gateway refuses leaves the claim waiting for sign-off with reason `gateway`, and a handler's sign-off then pays it once, with their name and the time (graph test and backend test). `hold_for_sign_off` answers 409 for a claim that isn't approved and unpaid, and 401 to a handler's sign-in.
- [x] The three variables are read when a claim graph is built: a test sets them after the modules are imported.
- [x] After a Gateway call the main thread still has an event loop, so the Mangum tests pass in the same process.
- [x] `PaymentPanel` shows the right sentence for each reason (vitest).
- [x] `npm run check` passes with `.env` moved out of the way. `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md` (the rule on how the agent reaches the backend: one module for each route) and `docs/STATUS.md` describe it. Commit.

## Phase 2: The context layer

- `context/files.py`: reads the YAML files and the two documents once, with each file's source (system, owner, reviewed date) and each document's version from its front matter.
- `context/documents.py`: splits each document at `^## (\d+)\. (.+)$` into sections tagged with document, number and title, and searches and reads them. Front matter is never part of a section.
- `context/lookups.py`: `lookup_term`, `describe_fields`, `get_plan`, `get_claim_rules` and `search_reference_data`. `context/server.py` registers all seven tools, read-only, each with a one-line docstring and no optional input, builds the stateless JSON FastMCP server (`build_server()`), and holds `handler`: a fresh server for each request under Mangum with `lifespan="auto"`, and DNS rebinding protection off. `context/__main__.py` serves it at `http://127.0.0.1:8006/mcp`. Every answer names its file and the file's source.
- `pyproject.toml`: a `context` dependency group, `pyyaml`, `mcp` and `langgraph-checkpoint-aws` (Phase 4) in the project's dependencies, `pyyaml` in the `server` group too, since `backend/db.py` imports `seed_data`; ruff, pyright, pytest and coverage take in `context/`. `package.json`: `check:context` (the server imports with only that group, isolated), in `npm run check`; `dev:context`, so `npm run dev` starts it.
- `backend/seed_data.py`: reads `context/plans.yaml` (whose values equal `data/plans.json`'s) and the two documents, into a `documents` table (document, version, text) in place of `document_sections`. `data/plans.json` and the two documents stay in `data/`, unread. `backend/main.py` and `reference.py` lose `list_sections` and `get_section`; `AGENT_OPERATIONS` has four.
- `agent/tools.py`: the context layer's seven tools as thin layers over the route's context target. `data/claim_instructions.md` (version 1) and the sentence in `agent/improver.py`'s instructions that lists the claim agent's tools name them.
- `agent/tests/test_structure.py`: only `seed_data.py` reads `context/`'s files on the app's side.

**Success criteria**

- [x] Each tool is called against the real files in `context/`: a known term in any case, an unknown term (which lists the terms), each record's fields, each plan, the claim rules, a reference-data search with every word, a document search, a section read, and a section that doesn't exist. Every answer names its file and source.
- [x] A test lists the tools: seven, all read-only, each with a one-line description and no optional input.
- [x] A test calls `context.server.handler` with Function URL events, with a Function URL's host, twice in one process, listing the tools and then calling one, and both succeed.
- [x] `npm run check:context` passes, and fails when an import is added that the group lacks (tried once and undone).
- [x] The agent's API document test expects four operations. After seeding, the plans match `plans.yaml` and the two documents are in `documents` with versions `2026.1` and `2026.2`.
- [x] With `npm run dev` running, the claim agent's tools from the context layer answer on the direct route (a test with the real server on a local port).
- [x] `npm run check` passes with `.env` away. `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md` and `data/README.md` describe the layer. Commit.

## Phase 3: A complete decision record

- `backend/calculations.py`: keeps the latest calculation of a claim's current attempt (`payout_calculations`, one per claim and `thread`) and reads it. `payouts.py` stays the pure rules.
- `calculate_payout` moves under the claim and keeps its result. `backend/decision_record.py` holds the decision's request model with section 14's checks, each message naming section 14: a blank reason, section or maker, an approval that pays nothing, a decline or referral that pays something. They run before the claim is looked at. `claims.decide` adds the check that an approval has a calculation on file for this attempt and a payout equal to it (`Invalid`, 422). The claim then holds `calculation`, `decided_by`, `decided_on` and `manual_version` (from the `documents` table), and a sign-off still adds who and when.
- `agent/`: the agent fills in `decided_by` (the UnderCover Agent with its configuration's version, or the security check for the check's referrals); the model never sees it.
- One shared helper for each suite records a matching calculation first and sends the maker: `backend/tests/`, `agent/tests/` and `e2e/decisions.ts`. The existing tests use it rather than change their payouts.

**Success criteria**

- [x] Tests cover each refusal and that it names section 14, a complete approval with its calculation, maker, time and version, a decline with no calculation, a referral by the check with the maker "Security check", and a sign-off adding who and when.
- [x] A blank reason gets the same 422 on any claim, including one that doesn't exist.
- [x] A calculation kept for one attempt is not accepted for the next after a requeue (test).
- [x] The agent's API document still has `Amount` as a `number` and the decision as a `string`, and `decided_by` as a string (the document tests).
- [x] `npm run check` passes with `.env` away, the end-to-end tests included. `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the record. Commit.

## Phase 4: Memory of each customer

- `agent/memory.py`: the agent's memory of a customer, on `AgentCoreMemoryStore` in the AWS CLI's region. Saving writes the two events with the customer as actor and the claim as session; searching covers only that customer's memories and leaves out the claim in hand. The story and the documents are never saved.
- `agent/claim_nodes.py`: a `remember` node after the decision is read back, in the graph only when memory is on and the claim isn't an evaluation's copy. `agent/tools.py`: `search_memory(query)`, in the claim's tool list only then. A failed save logs a warning and the claim keeps its decision, and a failed search reaches the model as a refusal.
- `data/claim_instructions.md` names the memory as a resource to use when the agent has it, so a run without memory isn't told of a tool it lacks.

**Success criteria**

- [x] With a stand-in store: the two events are saved after a decision, nothing for a claim the check referred or for an evaluation's copy, a search stays within the claim's customer and leaves out the claim in hand, and there is no memory tool when memory is off.
- [x] A claim carried on after a restart doesn't save twice (graph test).
- [x] With the store failing, the decision stands and a warning is logged; a failed search is a refusal.
- [x] `npm run check` passes with `.env` away. `docs/SPEC.md`, `docs/TECH_STACK.md` and `docs/STATUS.md` describe the memory. Commit.

## Phase 5: Every step on the claim page

- Backend: `claim_steps` gains a `kind` and `data`; `record_step` and the steps route carry them, and an unknown kind is a 422. Reseeding applies it, as `docs/STATUS.md` says.
- `agent/step_recording.py`: a `wrap_tool_call` that records each tool call named as its route names it, each lookup with what was looked up and its file's source, each memory search with what it found, and each refusal with its source (the app, the context layer, section 14 or the Gateway). The memory save is recorded by the `remember` node. The tools stop recording steps themselves.
- `dashboard/src/types.ts` and `api.ts`: the step kinds, checked, with the calculation's amounts converted to cents there and nowhere else.
- `dashboard/src/components/StepList.tsx` (a refusal stands out), `ContextUsed.tsx` (each lookup once, grouped by file with its source) and `DecisionPanel.tsx` (the whole record, the calculation line by line); `ClaimPage.tsx` composes them, in the brand's colors and plain words.

**Success criteria**

- [x] Tests cover each kind of step in the recorder, in the steps route and in `StepList`, and the Context used panel's grouping, and the decision panel with a calculation.
- [x] A Playwright end-to-end spec shows a claim's tool calls, a lookup with its file and source, a refusal standing out, the Context used panel and the decision with its calculation, with the data placed through the backend as the other specs do.
- [x] `npm run check` passes with `.env` away. `docs/SPEC.md` and `docs/STATUS.md` describe the page. Commit.

## Phase 6: Live checks and the last of the documents

Run after you reseed once. You stop `npm run dev` and run `npm run seed`, then start `npm run dev` again; I don't reseed.

**Success criteria**

- [ ] `npm run dev` starts the backend, the agent's service, the dashboard and the context layer; a `tools/list` call to `http://127.0.0.1:8006/mcp` returns the seven tools.
- [ ] On the direct route with memory off, `uv run -m agent CLM-1001` decides as before, and `uv run -m agent CLM-1005` then `CLM-1006` each record a complete decision; I report what each decided.
- [ ] A dispatch at N=25 works the rest of the queue as before, and CLM-1901 is referred by the check with the maker "Security check".
- [ ] An evaluation of the evaluation set's five tiny claims runs as before and flags none.
- [ ] Dana Whitfield signs in (Playwright MCP, `HANDLER_PASSWORD` kept out of the transcript) and sees on CLM-1005's and CLM-1006's pages the tool calls, the lookups with where each came from, the Context used panel and the decision with its calculation.
- [ ] I report what the live runs spent, from the dashboard's totals.
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md` (with the brief's Deployment section: the context layer's package, handler and Function URL, and the agent's three settings), `docs/PROCESS.md`, `docs/CODE_STANDARDS.md`, `docs/STATUS.md` and `data/README.md` describe the product as it now is.
- [ ] `npm run check` is green with `.env` moved out of the way, with the tests from every phase. A final review of the whole change against the checklist in `docs/CODE_STANDARDS.md`. Commit. I don't push.

## Things I'd like you to look at

- Four operations in the agent's API document, against the brief's six.
- The context layer's `search_documents` being new code, since the app never had one.
- Keeping `policy_reference` and `decided_on` beside the dictionary's `section` and `decided_at`.
- Editing version 1's text in `data/claim_instructions.md`, so reseeding applies it, in place of proposing a new version.
- The memory sentence being conditional, so a run with no memory isn't told about a tool it lacks.
- `UNDERCOVER_BACKEND` against the notebook's `UNDERCOVER_API`.
- The failed memory save logging a warning and carrying on. It is a deliberate exception to rule 13 in `docs/CODE_STANDARDS.md`, which the brief asks for, and I'll say why in the code.
- `hold_for_sign_off`, an agent-only operation that moves a claim from decided to waiting for sign-off, which no route does today.
- That the Gateway, the Lambda functions and the Memory are checked only by stand-ins and tests, since nothing here creates anything on AWS.
