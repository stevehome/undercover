# Plan: sending claims back and the agent on AgentCore Runtime

Builds the four steps in `docs/RUNTIME.md`, one phase each, in its order: the claim approval comes back as a pause the agent can be resumed from, a senior handler's send back, the agent as an AgentCore app, and the app keeping one run at a time. A fifth phase holds the live checks and the last of the documents. Nothing here creates anything on AWS: Runtime and Identity are covered by stand-ins and tests, and your notebook deploys the real ones later.

SIDENOTE: For consistency with the course, please read `labs/week3day4_lab2.ipynb`, which deploys the agent on AgentCore Runtime and points the app at it, without running it. Where the notebook and this document differ, follow this document. The pause in step 1 was in the course's build for self-improvement, before the security build took it out: `git show week2day5-end:agent/harness.py` has its `wait_for_sign_off` node, and `git show week2day5-end:agent/service.py` its `resume_claim` route. Lab 1's `agentcore dev` also serves on port 8080, so stop it before `npm run dev`. Include this sidenote in your plan too.

I have read the notebook, the two reference files at `origin/week2day5-end` (`harness.py`'s `wait_for_sign_off` and `service.py`'s `resume_claim`, as the brief asks, and nothing else on that branch), and the platform team's `agentcore/` and `runtime/`. From the notebook I take the shape of the deployment: one runtime, `agent`, with its three credentials in Identity and its three settings from `agentcore/.env.local`; the app sending each request as a payload in a new session; `agentcore dev` on 8080; and a teardown that puts the repo's configuration back. Nothing is built from `week2day5-end`: the pause it shows is already in our graph, in a form I describe next.

## Where the build differs from the brief's notes

The brief's notes come from Ed's build, and ours took a different path in places. I follow the intent. These are the places, so you can correct me before I build.

- **The pause already exists, in part.** Our graph has an `approval` node that waits with `interrupt()`, which `week2day5-end`'s `wait_for_sign_off` is the ancestor of, and the service still has a `resume_claim` route that the backend no longer calls. What is missing is what step 1 asks for: a payment the Gateway refused ends the graph today instead of pausing, an evaluation's copy pauses where it should end, "paused" is read from `state.next` where the notes say to read `interrupts`, and the resume doesn't read an answer from the app. Step 1 is smaller than the brief expects, and step 2 does the heavy part of the pause.
- **Where the graph is.** The notes say `agent/harness.py`; ours is `agent/claim_graph.py` and `agent/claim_nodes.py` (`harness.py` only builds the models). `after_tools` is our `settle`, whose edges are `after_settle`, `after_remember` and so on. The dispatcher's `list_claims` reads a run's claims from the app: the app chooses them when it creates the run (`backend/runs.py`, `_claims_to_dispatch`), which is where sent-back claims join.
- **The memory is saved at the end.** Today `remember` runs before the payment or the sign-off, so a decision a handler sends back would already be in the customer's memory. The brief wants a claim saved to memory after a sign-off, so I make `remember` the last node on every path: after a decline or referral, a payment, and a sign-off. The save is still once per claim, in code, after the decision is final.
- **Names.** The sign-off panel is `PaymentPanel.tsx`'s `SignOff` (no `SignOffForm.tsx`); the check on the handler is `senior_handler` in `backend/auth.py` (no `SignsOffOverTheLimit`); a claim's decision is columns on `claims` (no decisions table); the agent's stand-in for the end-to-end tests is `e2e/agentStandIn.mjs`; and there is no `backend/instructions/claim.md`: the instructions are version 1 in `data/claim_instructions.md`, which says "Record your decision by calling decide_claim once", the sentence a send back changes. It reaches the database only on a reseed, and a version the improver made carries its own text, which is why the note's message is in the agent's code and not its instructions (step 2.5).
- **The agent's timeouts.** The notes say the app's call has a 10-second timeout. Ours has 5 seconds to connect and 70 to read, since today the agent creates the run before it answers (`backend/agent_service.py`). Once the app creates the run itself (step 4) the agent answers at once, so I use the brief's 10 seconds and take the 70 out.
- **The agent's runs and rounds come from the app already, through its key.** The backend's logic is `runs.create_dispatch`, `rounds.create_round` and `proposals.record_decision`, which the service reaches over the agent's API as `/api/runs/dispatch`, `/api/runs/evaluation`, `/api/improver/rounds` and the proposal decision. Step 4 turns this round: the app calls them itself, and those routes go. There is no column for why a run stopped; step 4 adds one for runs and rounds.
- **What the run is recorded with.** The agent chooses a run's model today (`harness.model_settings`), and the app records it. When the app creates the run it records the current configuration's model and effort itself, or `MODEL_NAME` with effort `default` as the backend's model list already does. The improver's model is a constant in `agent/harness.py` (`IMPROVER_MODEL`, `IMPROVER_EFFORT`); the app needs it to record a round's stretch. I move it into `data/improvement.json` and have the agent read it from the round's record, so it is written once. This is the one place I add data for the brief.
- **A payload's inputs are the routes'.** The brief's example is `{"operation": "start_dispatch", "agents": 25}`, and its own rule is that the inputs are the ones each route takes today. Ours takes `concurrency`, so the payload is `{"operation": "start_dispatch", "concurrency": 25}` until step 4 replaces it with `work_run`.
- **`stop_round`.** The brief's operations are "the service's", and the service has a `stop_round` that only acknowledges: a stopped round is refused by the app's own records already. On Runtime each call starts a session, so telling the agent that a round stopped would cost a session for nothing. I leave `stop_round` out of the agent's operations and keep the app's own stop. Say so if you want it kept.
- **The app's address.** The platform team's deployment gives the agent `UNDERCOVER_API` as the app's address (`agentcore/cdk/lib/cdk-stack.ts`, `SETTINGS`), but the agent reads `UNDERCOVER_BACKEND` and builds its HTTP client when `agent/backend_http.py` is imported. On Runtime the agent would call `localhost:8000`, which is the thing the brief means by "if something in them stops the agent working, say so". I change the product to fit, since `agentcore/` is theirs: the agent reads `UNDERCOVER_API` when asked (`agent/endpoints.py`, which already reads its three settings that way), and the client is made on first use. The dashboard's Vite proxy keeps `UNDERCOVER_BACKEND`, which is another thing.
- **Credentials in Identity.** I can't see from `agentcore.json` or `policy.json` whether the runtime's role may fetch the three credentials from AgentCore Identity; the CLI's CDK construct may add that itself. Your lab 2 settles it on a real deploy, and the plan builds nothing for it. If it doesn't, the platform team's `policy.json` needs a statement for it, and I'd report that to you rather than edit the file.
- **The two folders aren't in git.** `agentcore/` and `runtime/` are untracked in your tree, as they came from `setup/setup_week3day4/`. Phase 3's commit adds them exactly as they are, with `agentcore/.env.local` kept out by `.gitignore`'s `.env.*`.

## Design

- **One module for the work, three ways to ask for it.** What an operation does (check, accept or refuse, work in the background) is in `agent/operations.py`, which knows nothing of how it was asked. The step 1 and 2 phases reach it through the service's routes that exist today; Phase 3 makes the AgentCore app its one entry point. Nothing is written twice and nothing is thrown away.
- **Paused means an interrupt waiting.** `graph.get_state(config).interrupts` says so, in `agent/paused.py`, not `next`, which names the pause one step early. The answer the graph is resumed with is read from the app's record of the claim, never from the request: a claim paid with a sign-off, or sent back with a note.
- **The send back is a status, a record and a conditional update.** `sent back` joins the claim statuses. The decision that was sent back is kept in its own table, with its note, who and when, so a claim can be sent back more than once. One conditional `UPDATE` on `status = 'waiting for sign-off'` decides between a sign-off and a send back at the same moment, as the sign-off's does today; the record, the cleared decision and the step go in that same transaction, which holds the one connection.
- **The note's message is code.** `agent/review_message.py` builds the message the model reads, and the graph's `approval` node adds it. It says the note is a senior handler's review of the decision, to be checked against the policy wording and the claims manual like everything else, and a referral with the reason when the wording doesn't support it. A new version of the instructions can't drop it.
- **Taking a claim happens once.** `take_claim` moves a sent-back claim to in progress by one conditional update only the agent's key can call; the second caller gets a 409 and leaves the claim alone. A resume then tells the app every minute that it is working, and a dispatch leaves alone a claim in progress whose resume the app has heard from in the last five minutes.
- **Getting ready is lazy and once.** `agent/readiness.py` does what the service's lifespan does today, on the first request, once in the process, behind a lock: reseed Python's random numbers on Runtime, fetch the credentials into their settings (`agent/credentials.py`, the one module that imports `bedrock_agentcore.identity`), check the agent's key and open the checkpoint pool. If it fails, that request answers the error and the next tries again. Importing `agent.entrypoint` opens nothing.
- **The work holds the session.** `agent/background_work.py` registers each piece of work with the AgentCore app as an async task before the operation answers, and completes it in a `finally`, so Runtime's ping says `HealthyBusy` while anything is going. The AgentCore app's two methods are passed in, so no module imports `entrypoint.py`.
- **The app asks in one place.** `backend/agent_service.py` makes the request on one of two routes, and says what happened in one of four ways: taken, refused (the agent's own refusal, passed on as a 409), not taken (never sent or never connected, or an error answer: undone and an error to the handler) or unknown (a timeout or a cut-off answer: nothing changed, and the handler is told to reload). `backend/agent_laptop.py` posts with the key to `UNDERCOVER_AGENT`; `backend/agent_runtime.py` is the only module that imports boto3 for this, one attempt, a new session id of 33 characters or more each time. Retrying could start the same work twice.
- **The app starts the work.** `backend/starts.py` does what the agent's service did: sweeps work gone quiet, creates the run, the round or the review in a short transaction it commits, then asks the agent for the work by id, and undoes the creation when the agent didn't take it. The unique index on running runs with no parent that the database already has is the lock; a conditional update does the sweep. A request holds one connection at a time, which `backend/tests/test_connections.py` already checks for the main flows.
- **The app hears about live work.** `heard_from_on` on runs and rounds, and `resume_heard_on` on claims, are set by three agent-only operations, one for each kind of work. The agent's `agent/heartbeat.py` calls the right one every minute from a thread while it works, as the lease's renewal does. Work not heard for five minutes, counting from the later of when the app started it and the last word, is stopped by the next start, with the reason "The agent stopped answering". A round's word covers its evaluation.
- **The checks.** `runtime` joins the dependency groups, with its own import check beside the server's and the context's; ruff and pyright cover `runtime/`; `boto3` joins the `server` group.

## Phase 1: The approval comes back (step 1)

The graph pauses for every payout waiting for a sign-off, the app asks the agent to resume it, and the agent reads what to do from the app's record. The send back's half of the answer is Phase 2.

- `agent/claim_graph.py` and `claim_nodes.py`: `settle` sends an approval over the limit to `approval`, a payout within it to `pay`, and anything else to `remember`. `pay` sends a payment the Gateway refused to `approval`, after holding it. `approval` pauses, and a sign-off sends it on to `remember`, the last node of every path. An evaluation's copy never reaches `approval`: it ends, as today (`ClaimContext` carries whether the claim is a copy). Nothing goes before `interrupt()` in `approval`, since it runs again from the top.
- `agent/paused.py`: whether a claim's thread has an interrupt waiting, and what it waits for.
- `agent/resumption.py`: the `resume_claim` operation's logic. It refuses a claim that isn't paused, with the reason, and otherwise answers at once and works the claim on a thread of its own, outside any run, on the claim agents of the current version. It reads the answer from the app's record: a sign-off, here, and a send back in Phase 2. `agent/service.py`'s route calls it.
- `agent/agents.py`: `_work` takes its answer from the app's record through one function, so a dispatch and a resume do the same.
- `backend/agent_service.py` and `backend/main.py`: a sign-off asks the agent to resume the claim, as a background task, after the sign-off and its payment are saved. The sign-off answers with the updated claim whatever happens to the call; a failure or a timeout is logged as a warning and nothing is undone.
- `docs/STATUS.md`: the known gap, a sign-off the agent never learned of leaves the claim's thread paused and its memory unsaved.

**Success criteria**

- [ ] A test with stand-ins: an approval over the limit pauses with its place saved in the checkpoint, and the claim shows as waiting for sign-off; the thread has one interrupt waiting.
- [ ] A payment the Gateway refuses pauses the same way, after the hold.
- [ ] An evaluation's copy over the limit doesn't pause: its work ends and its saved progress is cleared, as today.
- [ ] A resume after a sign-off ends the work without paying again, and the claim is saved to a stand-in memory once; a decline, a payment and a pause each save it once, at the end, and a claim the check referred never.
- [ ] `resume_claim` refuses a claim that isn't paused, one that is paused but not signed off and one that doesn't exist, each with its reason, and works a signed-off one beside a dispatch without waiting for it.
- [ ] A sign-off pays and answers with the claim when the agent can't be reached, and the app logs a warning; a test with a stand-in agent that is down, one that times out and one that answers.
- [ ] With `npm run dev` running, a claim over the limit pauses, and signing it off on the dashboard pays it and ends the agent's work (Playwright MCP, as Dana Whitfield), with the claim's steps ending "Signed off by Dana Whitfield".
- [ ] `npm run check` passes with `.env` moved out of the way. `docs/STATUS.md` describes it. Commit.

## Phase 2: Sign off or send back (step 2)

- `backend/statuses.py` and `tables.py`: `ClaimStatus.SENT_BACK`; a `sent_back_decisions` table (the decision with its payout, reason, section, maker, time, calculation and manual version, the note, who sent it back and when); `resume_heard_on` on `claims`.
- `backend/sent_back.py`: `send_back_claim`, which checks the handler is senior, the note is not blank and at most 1,000 characters, and refuses an evaluation's copy and a claim that isn't waiting for sign-off (409). One conditional `UPDATE` on the waiting status moves the claim to sent back and clears its decision, its calculation for the attempt and its hold reason; the record and the note's step go in that transaction. `take_claim` is the agent's conditional update from sent back to in progress, which sets `resume_heard_on`.
- `backend/claims.py` and `backend/runs.py`: `get_full` returns the sent-back decisions; a decision on a sent-back claim goes through the same checks as any other; a dispatch takes sent-back claims with the waiting ones, and leaves alone a claim in progress whose resume the app heard from in the last five minutes. The summary of a run counts nothing new.
- `backend/main.py`: `send_back_claim` (a senior handler), `take_claim` and the resume's heartbeat (the agent's key). Neither of the agent's is in the claim agent's API document.
- `agent/review_message.py`, `claim_nodes.py` and `claim_graph.py`: after a send back, `approval` forgets the earlier decision and its payout, resets the model-call count, adds the message and goes back to `agent`. The decision can be new and can wait again.
- `agent/resumption.py` and `agents.py`: a resume or a dispatch takes a sent-back claim first, and works it if it got it. Resumes run `agent/heartbeat.py`'s every-minute word while they work.
- `data/claim_instructions.md`: says a handler may send a decision back with a note, in place of "once".
- `dashboard/src/components/PaymentPanel.tsx` and a new `SendBackForm.tsx`: Sign off and Send back beside each other for a senior handler, with a note field that is required, up to 1,000 characters, on a confirmation. `DecisionPanel.tsx` shows each decision that was sent back with its note, who and when, beside the current one; the claim page says when a claim is waiting for the next dispatch. `StatusPill.tsx` and the queue know `sent back`; `types.ts` and `api.ts` read the new fields and money as cents; the words follow `docs/BRAND.md`.
- `docs/SPEC.md`: the send back, in place of "A handler can only sign off".

**Success criteria**

- [ ] Backend tests: a send back refused for a non-senior handler, a blank note, a note over 1,000 characters, an evaluation's copy, a claim that isn't waiting for sign-off, and a claim already sent back; the decision kept with its note, who and when, and the claim's own decision cleared.
- [ ] A sign-off and a send back at the same moment: exactly one goes through, whichever is first, and the other is a 409 (two requests, in threads).
- [ ] A sent-back claim is taken once when a resume and a dispatch both ask; the second gets a 409 and leaves it.
- [ ] A dispatch started while a resume is working leaves its claim alone; the same dispatch takes a sent-back claim nobody has taken.
- [ ] A new decision after a send back is paid when within the limit, waits for sign-off again when over it, and an approval without a fresh calculation is refused; a claim can be sent back twice.
- [ ] A send back the agent never received: the next dispatch works the claim, and a dispatch that carries on a claim whose thread is still paused resumes it with the note.
- [ ] A graph test with a scripted model: after a send back the model sees the message naming the handler and how to treat the note, its model-call count starts again, and nothing pays the earlier decision.
- [ ] vitest: the two buttons for a senior handler and neither for the other; the note required; each sent-back decision on the claim page; `sent back` in the queue.
- [ ] With `npm run dev` running, a claim sent back with a note is decided again by the agent, and the claim page shows both decisions and the note (Playwright MCP, as Dana Whitfield).
- [ ] `npm run check` passes with `.env` moved out of the way. `docs/SPEC.md` and `docs/STATUS.md` describe it. Commit.

## Phase 3: The agent as an AgentCore app (step 3)

- `agent/entrypoint.py`: `app = BedrockAgentCoreApp()` and one entrypoint that takes the payload and its context and calls `operations.handle`. It is short and nothing else is in it.
- `agent/operations.py`: the operations by their ids (`start_dispatch` becomes step 4's `work_run` in the next phase; here they are the service's, with `resume_claim` and `health`), each with a pydantic model for its inputs, so a payload with an input missing or wrong, or an operation it doesn't know, is a 400 that says what is wrong. Each answers `{"accepted": true}` or `{"refused": "<reason>"}`, and the health check `{"healthy": true}`.
- `agent/background_work.py`, `readiness.py`, `credentials.py`, `key_check.py`: as in the design. The key check refuses off Runtime with a 401 apart from the health check; on Runtime it asks for nothing. The agent knows it is on Runtime from the credentials' settings.
- `agent/endpoints.py` and `backend_http.py`: the app's address is `UNDERCOVER_API`, read when asked, and the client made on first use.
- `agent/checkpoint.py`: `prepare_threshold=None`.
- `agent/service.py` goes, with its tests; `package.json`'s `dev:agent` serves `agent.entrypoint:app` with uvicorn on 127.0.0.1:8080 with reload.
- `backend/agent_service.py`, `agent_laptop.py`, `agent_runtime.py`, `backend/errors.py`: the two routes, with the four outcomes, 10 seconds on the laptop, 5 to connect and 20 to read on Runtime. `UNDERCOVER_AGENT` defaults to `http://127.0.0.1:8080`; `UNDERCOVER_AGENT_RUNTIME` is the runtime's ARN.
- `pyproject.toml` and `package.json`: `bedrock-agentcore` joins the dependencies and a `runtime` group holds exactly what the agent needs on Runtime; `boto3` joins `server`; `check:runtime` imports `runtime.main` in a throwaway environment with only that group, and `npm run check` runs it; ruff and pyright include `runtime/`.
- `playwright.config.ts` and `e2e/agentStandIn.mjs`: the stand-in answers `/invocations` and `/ping` and records each payload; `UNDERCOVER_AGENT_RUNTIME` is blank for the end-to-end backend and for pytest's setup.
- `agentcore/` and `runtime/`: added to git as the platform team wrote them.
- `docs/TECH_STACK.md`: the Deployment section gets the agent on Runtime.

**Success criteria**

- [ ] Tests through Starlette's `TestClient`, with stand-ins for the work and for Identity: importing the agent opens nothing and reads no setting; on Runtime the first request fetches each credential into its setting once, and a second request doesn't; each operation accepts work and refuses it; a payload with an input missing, a wrong input and an unknown operation each get a 400 that says what; the ping is `HealthyBusy` while work is going and `Healthy` once it has finished or failed; a request without the key is refused off Runtime and let through on Runtime; the health check works without the key and only once the agent is ready; a failed getting ready answers its error and the next request tries again.
- [ ] Tests of the app's two routes, with stand-ins: the key on the laptop route, the session id (33 characters or more, new each time) on the Runtime route, and on both the payload, an acceptance, a refusal passed on as a 409, a failed connection, an error answer, and a timeout or a cut-off answer that changes nothing and tells the handler to reload; one attempt only.
- [ ] A structure test keeps `bedrock_agentcore.identity` to `credentials.py`, boto3's Runtime client to `agent_runtime.py` and the app's address to `endpoints.py` on the agent's side.
- [ ] `npm run check:runtime` passes inside `npm run check`.
- [ ] With `npm run dev` stopped, `uv run --env-file .env --isolated --only-group runtime python -m runtime.main` serves the agent on 8080, and `{"operation": "health"}` posted to `/invocations` answers `{"healthy": true}`.
- [ ] `npm run check` passes with `.env` moved out of the way. `docs/TECH_STACK.md` and `docs/STATUS.md` describe it. Commit.

## Phase 4: The app keeps one run at a time (step 4)

The largest phase: the app takes over creating the work, the agent takes it by id, and the app learns when work went quiet.

- `backend/starts.py`: the start of a dispatch, an evaluation, a round and a handler's review, in the design's order: sweep what went quiet, create in one transaction, ask the agent, undo what it didn't take. A refusal names what is going ("A dispatch is already running", "An evaluation", "An improvement round").
- `backend/runs.py`, `rounds.py`, `proposals.py`: `stopped_reason` on runs and rounds, `heard_from_on` on both, the sweep as a conditional update, the undo of each kind (a run stopped with the reason, a new round stopped, a review cleared: the proposal pending again, its new version taken out and the round's stage put back, with the stretch stopped), and the heartbeat operations. A round's stretch records the improver's model from `data/improvement.json`.
- `backend/main.py`: the three start routes call `starts`; the agent's `create_dispatch`, `create_evaluation` and `create_round` routes, `stop-unfinished` and the proposal decision's agent hop go; `stop_run` by id, the heartbeats and `get_proposal` for the agent's key come in.
- `agent/operations.py` and `agent/work_requests.py`: `work_run`, `work_round` and `carry_round_on` take the place of the four that start work; each refuses a run that isn't running or a round that isn't open; `carry_round_on` reads the review and its reason from the app. The agent no longer creates runs or rounds, no longer records reviews and no longer marks anything stopped when it gets ready.
- `agent/heartbeat.py`: the every-minute word for a run, a round and a resumed claim. When a run's or a round's work fails the agent stops that run or round by its id, and stopping a round stops its running evaluation.
- `agent/harness.py` and `rounds.py`: the improver's model comes from the round's record.
- `dashboard/`: a run's and a round's reason for stopping, in the places each is shown.
- `e2e/agentStandIn.mjs`: finishes or stops the work it is given, through the app's address and the agent's key, so a later start isn't refused.

**Success criteria**

- [ ] Backend tests: a second start refused, naming what is going, while a dispatch, an evaluation and a working round are going; a round waiting for a review doesn't hold a dispatch; two starts at the same moment, in threads, with exactly one going ahead; a start after work went quiet for five minutes stops it with the reason and goes ahead, and a round's quiet stops its evaluation too; work heard from a minute ago is left alone; the app never stops a round's evaluation on its own.
- [ ] A start the agent didn't take (never connected, an error answer, a refusal) is undone for each kind: the run stopped, the new round stopped, the review cleared with its version gone and the proposal pending again; a timeout leaves the work going. The handler gets the answer they got before, or the reload message.
- [ ] A failed run stops only itself, and another running claim's resume, run or round is untouched; a resume runs beside a dispatch.
- [ ] `backend/tests/test_connections.py` covers the new flows: no start, undo or send back holds two connections.
- [ ] The agent tests: `work_run` refuses a run that isn't running and a round that isn't open; the agent marks nothing stopped when it gets ready; `carry_round_on` reads the review from the app; the improver's model is the round's.
- [ ] `npm run e2e` passes with the app creating runs, rounds and reviews.
- [ ] With `npm run dev` running, a dispatch at N=25 works the queue, and starting another while it runs is refused on the dashboard (Playwright MCP, as Dana Whitfield).
- [ ] `npm run check` passes with `.env` moved out of the way. `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md` and `docs/STATUS.md` describe it. Commit.

## Phase 5: Live checks and the last of the documents

You run `npm run seed` once with `npm run dev` stopped, and start it again. Everything is on the default model, the direct route and with memory off.

- A dispatch at N=25 that works the queue, with the pool of four connections as it is.
- As Dana Whitfield: one claim over the limit sent back with a note and decided again, and another signed off. Both claims' pages are checked through the Playwright MCP server, and the page shows both decisions and the note on the first.
- An evaluation of the evaluation set's five tiny claims.
- `uv run --env-file .env --isolated --only-group runtime python -m runtime.main` answers the health check.
- What the runs spent.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/CODE_STANDARDS.md` and `docs/STATUS.md` describe the product as it now is, including that the dispatcher's known gap resolves itself: work the app hasn't heard from for five minutes is stopped by the next start.

**Success criteria**

- [ ] A dispatch at N=25 finishes and its summary matches the claims' pages; the backend stays up (`/api/health` answers while it runs).
- [ ] One claim sent back by Dana is decided again by the agent, and its page shows the earlier decision, the note and the new decision; another is signed off and paid once, with her name and the time.
- [ ] The tiny evaluation finishes, graded, and the check clears all five.
- [ ] The health check through `runtime.main` answers `{"healthy": true}`.
- [ ] The cost of each run is reported. `npm run check` passes with `.env` moved out of the way, and the whole change is reviewed once more against the checklist in `docs/CODE_STANDARDS.md`, including the code the build touched outside its own area. Commit.

## Things I'd like you to look at

- **The memory is saved last** (above): after a payment or a sign-off, not after the decision. A claim whose payment keeps failing isn't saved until it is paid.
- **`stop_round` is not an agent operation.** Say so if you'd rather keep it.
- **`UNDERCOVER_BACKEND` becomes `UNDERCOVER_API` for the agent.** Your lab notebooks already use the new name, and the platform team's deployment needs it.
- **The improver's model moves into `data/improvement.json`**, so the app can record a round's stretch, and the agent reads it back.
- **A send back also drops the attempt's calculation**, so the new approval needs a new one. Its numbers stay with the sent-back record.
- **`data/claim_instructions.md` changes version 1's text only.** Already-seeded databases and the improver's later versions keep the old words until a reseed or a new version; the message in the agent's code covers both.
- **Nothing is checked against AWS.** Runtime, Identity and the Gateway are stand-ins. What can only be settled on a real deploy: whether the runtime's role may read its credentials, and whether a session's work survives the one-minute idle timeout as the notes say it did.
- **`agentcore/` and `runtime/` go into git unchanged**, as they are untracked now.
