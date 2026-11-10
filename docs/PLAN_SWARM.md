# Plan: a swarm of claim agents and a scoreboard

Builds `docs/SWARM.md`: GPT-6 Luna as the default model, cost and time recorded for every claim, a dispatcher with no model in place of the queue agent, dispatches started from the dashboard, evaluations on the two labelled sets, and a Scoreboard page.

SIDENOTE: For consistency with the course, please read `labs/week2day4.ipynb` and build the dispatcher in the same style as the lab. Where the lab and this brief differ, follow the brief.

I have read the lab. It gives the shape of the dispatcher: a state with a `results`-style reducer, a node that lists the claims, a conditional edge that returns one `Send` per claim, a worker node with a `RetryPolicy`, `max_concurrency` in the config, and OpenRouter's cost read from `response_metadata["token_usage"]["cost"]`. It also gives the measures for the scoreboard. Where the lab and the brief differ I follow the brief:

- The lab runs the whole swarm as one graph on one thread. Here each claim keeps its own thread and its own saved progress, and the dispatcher saves nothing.
- The lab keeps decisions in a dict and scores after the run. Here the backend holds the decisions and scores each evaluation from its own records.
- The lab's retry is one `RetryPolicy` for every error. Here it covers rate limits and timeouts only, and other errors fail the claim as they do today.

## What I found in the code

Places where the brief's notes on the current build don't match the code. I follow the brief's intent.

- There is no `write_todos` tool and no `backend/instructions/queue.md`. The queue agent's tools are `get_to_do`, `work_claim` and `finish_run` in `agent/tools.py`, its instructions are the `QUEUE_INSTRUCTIONS` string in `backend/instructions.py` (served at `/api/queue-instructions`), and its to-do list is the `runs` and `run_items` tables. Those are what goes, with `run_queue`, `carry_on`, `RunContext`, `AgentSpec` and `run_agent` in `harness.py`, and the to-do panel and queue-instructions section in the dashboard.
- The brief says the worker calls "one function in the harness". In this build `agent/harness.py` is generic on purpose (rule 10: it knows models, not claims). The function is `agents.decide_claim(claim_id, run_id)`, which already starts a claim or carries it on. I am treating `agents.py` as the brief's harness and I'll say so in `CODE_STANDARDS.md`.
- `uv run -m agent` takes `--claim CLM-1001` today. The brief wants `uv run -m agent CLM-1001`. The backend's `agent_process.py` starts the agent with `--claim` and changes with it.
- `work.py` already does the retry and give-up rules in plain Python: a failed claim is requeued on a new thread, tried once more, then left for a handler, and a stopped claim carries on without a new attempt. The dispatcher's worker reuses it, with rate limits and timeouts let through so `RetryPolicy` handles them.
- A claim lease already exists (`lease.py`). A dispatch "skips a claim the service is already resuming after a sign-off" by calling `decide_claim`, which returns at once when another agent holds the lease.
- The tests have no `e2e/run.spec.ts`. The run's to-do list is tested in `e2e/queue.spec.ts`, so that test goes and a new `e2e/run.spec.ts` covers the dispatch and the scoreboard.
- `agent/tests/test_structure.py` fails if any agent or backend module contains the word `evals`. Seeding has to read `data/evals/`, so the test changes to allow `seed_data.py` only, and new checks keep the answer key out of every claim operation (Phase 4).

## Design

**Dispatch and evaluation are both runs.** One `runs` table: `run_id`, `kind` (`dispatch` or `evaluation`), `status` (`running`, `finished` or `stopped`), `concurrency` (N), `eval_set` and `tiny` (evaluations only), `model`, `reasoning_effort`, and the start and finish times. A partial unique index on `status = 'running'` allows only one running run, on SQLite and on Postgres, so a second start is refused by the database and not by a check that could race. `run_claims` replaces `run_items`: one row per claim in the run, with its status, attempts and a one-line note.

**The dispatcher.** `agent/dispatcher.py`, a LangGraph graph with no model:

```
START -> list_claims -> (one Send per claim) -> work_claim -> END
```

- `list_claims` reads the run's claims from the backend. The backend chose them when it created the run: every claim in progress and every waiting claim, oldest submitted first.
- `work_claim` is the worker. It calls `work.work_claim`, which calls `agents.decide_claim(claim_id, run_id)`. That is the only place the dispatcher touches the claim agent, so later it can point at the agent in the cloud.
- `max_concurrency` in the config is N.
- `RetryPolicy(retry_on=(ModelRateLimitError, ModelTimeoutError))` (both from `langchain_core.exceptions`, which `langchain_openai` raises) on the worker. `decide_claim` and `work.py` let those two through without settling the claim, so a retry carries the claim on from its last saved step as the same attempt. That is safe because the backend never decides or pays a claim twice.
- When the retries run out, the node's `error_handler` (LangGraph's `add_node(..., error_handler=...)`, called with the state and a `NodeError`) marks the claim `still in progress` in the run and returns. The claim stays in progress for the next dispatch, and no error stops the dispatch.
- Any other error is handled inside `work.py` as today: the claim is requeued on a new thread and tried once more in the same dispatch, then left for a handler.

**Each claim keeps its own thread.** The thread is still `CLM-1001-1`. The dispatcher saves no progress of its own. If the service dies, the next dispatch finds the claims still in progress and carries them on from their checkpoints.

**Connections.** The agent process stays at 4. The checkpointer's pool grows from 2 to 4, and each claim run gets a `PostgresSaver` of its own on that shared pool, because one saver holds a lock around every read and write and 25 claim agents would take turns. The pool waits for a free connection (a long `timeout`) instead of failing. The backend's engine stays at 4 and also waits, since 25 claim agents call it at once. The lease's renewal threads call the backend, not the database.

**Cost and time.** Two backend tables, written through operations:

- `model_calls`: one row per model call with the claim, the run (null when there is none), the model, input, output and total tokens, and the cost.
- `work_segments`: one row per stretch of the agent working on a claim, with the claim, the run (null when there is none), and the start and finish. A claim paused for a sign-off ends a segment at the pause, and the resume after the sign-off starts a new one with no run, so a wait for a handler is never counted. A failed attempt still records its segment.

A run's totals are the sums of its own rows. The operations take `run_id` as a required field that may be null, because the API rules allow no optional inputs.

**Cost is stored in billionths of a dollar.** OpenRouter reports costs like `$0.000138675`, below a cent and to nine places (found in the first live run, which a six-place column refused), so the "whole cents in the database" rule for payouts can't hold. The database keeps whole billionths of a dollar, Python uses `Decimal`, and the wire carries a decimal string of up to nine places. This is a deliberate exception to rule 7 for model costs only; `STATUS.md` and `TECH_STACK.md` will say so. Please check this choice.

**Evaluations.** An evaluation works copies of claims through the same dispatcher and claim agent.

- Seeding stores the held-out claims in `held_out_claims` and the handlers' decisions in `answer_key` (set, claim id, `tiny`, decision, payout). No claim operation reads those tables, and the agent's service never asks for the decisions. The backend scores from them.
- Starting an evaluation copies the set's claims into `claims` as fresh `waiting` rows with new ids, `EVAL-<run id>-<source id>` (the id is written into the copy's record too), marked with `evaluation_run_id`. `run_claims` keeps the source id for scoring. The queue operations (`list_claims`, `list_unfinished_claims`, the dispatch's choice of claims) skip copies, so the queue and a dispatch never see them.
- An approval over the limit leaves a copy at the graph's `approval` pause. For an evaluation the worker counts that as finished and deletes the claim's saved progress. Nobody can sign off a copy: the backend refuses it with a 409, and the dashboard shows no sign-off form on a copy's page.
- The service marks any run still `running` as `stopped` when it starts, for dispatches and evaluations alike, so an evaluation that was cut short shows as stopped and is never carried on.

**Scoring.** `backend/scoring.py` holds pure functions on `Decimal`, with the lab's rules and the brief's: `decision_accuracy`; `accuracy` (decision matches and payout within a dollar); the cost of mistakes (a wrongful decline $1,500, a wrongful approval its payout, a needless referral $50, a wrong amount on a right approval the difference); the straight-through rate; model cost per claim; time per claim; and the time for the whole run. A claim the agent didn't decide counts as a referral with a payout of 0. The scoreboard computes the measures when it reads, from the records.

**Starting a run.** The dashboard calls the backend (`start_dispatch`, `start_evaluation`). The backend asks the agent's service through `backend/agent_service.py`, passing N and the set, and writes nothing the service needs before that. The service answers at once, or refuses with a 409 while a run is going. It creates the run through the backend, which enforces the one-running-run rule, and works in the background. If the service can't be reached the backend answers 503 "The agent's service isn't running" and the dashboard shows it. N is 1 to 25, checked by the request model.

**The default model.** `openai/gpt-6-luna` with reasoning effort `low`. With `MODEL_NAME` set, that model runs with no effort set, and a run records it as `none`. `harness.model_settings()` returns the name and the effort, used both to build the model and to record the run.

**Langfuse.** Each claim still has its own session. `tracing.trace` also takes the run's tag (`run-12`, since a dispatch and an evaluation never share an id) and puts it in `langfuse_tags` in the metadata, so a whole run is found by its tag.

## New dependencies

`langgraph>=1.2.20` is now named in `pyproject.toml` (it was only a transitive dependency): in 1.2.12 an error handled by a node's `error_handler` was still re-raised when a step ran several tasks, which is every dispatch, and 1.2.20 fixes it (shown with a small graph in both versions). The others are already there.

## Phase 1: GPT-6 Luna as the default, and cost and time

- `agent/harness.py`: `model_settings()` and the new default (still no claims in it).
- `backend/tables.py`, `backend/usage.py`: `model_calls` and `work_segments`, and `usage.py` records them and sums a run's totals. One job: cost and time records.
- `backend/main.py`: operations `record_model_call` and `record_work_segment`, each a thin call into `usage.py`.
- `agent/contexts.py`: `ClaimContext` gets `run_id: int | None`.
- `agent/claim_nodes.py`: the model node records each reply's tokens and cost.
- `agent/timing.py`: a context manager that records a work segment, failures included. `agent/agents.py` wraps each `graph.invoke` in it.
- `agent/api.py`: the two new calls.

Success criteria:

- [x] A stub-model run of a claim writes one `model_calls` row per model reply, with the tokens and cost from the reply, and the run's id when one is given and none when it is not.
- [x] A claim paused for a sign-off and resumed later has two segments, and the time between them is in neither. A test with a gap between the invokes shows the segments sum to less than the elapsed time.
- [x] A failed attempt still has its segment, and a run's totals include it.
- [x] Two runs' totals are separate, and the rows with no run belong to neither.
- [x] `harness.model_settings()` returns `openai/gpt-6-luna` and `low` by default, and `MODEL_NAME` gives that name and `none`.
- [ ] `uv run -m agent --claim CLM-1002` on the default model works one claim and its `model_calls` and `work_segments` rows exist on Supabase (checked through the Supabase MCP server). I report what it decided. (Not done: the first try wrote the table with a six-place cost and was refused; `npm run seed` is needed to rebuild the table and the sandbox denied it. Waiting for the user to reseed.)
- [x] I look at the reply shape of `MODEL_NAME=openrouter/free` before deciding how to read cost, and report what it returns. (Both it and GPT-6 Luna return `response_metadata["token_usage"]["cost"]`, `0` for the free model, and a model name that, for the free router, is the model it chose.)
- [x] `npm run check` is green.

## Phase 2: the dispatcher in place of the queue agent

- `backend/tables.py`, `backend/statuses.py`, `backend/runs.py`: `runs` and `run_claims` replace the to-do tables, with the partial unique index. `runs.py` creates a dispatch with its claims, updates a run's claim, finishes a run, marks unfinished runs stopped, and builds a run with its claims and totals.
- `backend/main.py`: the run operations, thin.
- `agent/dispatcher.py`: the graph above, and `run_dispatch(run_id, n)`. One job: working a run's claims with up to N at once.
- `agent/work.py`: reshaped for the dispatcher, with the rate-limit and timeout errors let through and the `error_handler`'s "still in progress" note.
- `agent/agents.py`: `decide_claim(claim_id, run_id=None, ...)` takes a saver of its own. `run_queue` and `carry_on` go.
- `agent/checkpoint.py`: the pool of 4, waiting for a connection, and a saver for each call.
- `agent/tracing.py`: the run's tag in `langfuse_tags`.
- `agent/__main__.py`: `uv run -m agent CLM-1001` only. `backend/agent_process.py` follows.
- `backend/db.py`: a pool timeout long enough that claim agents wait.
- Removed: the queue tools, `RunContext`, `AgentSpec` and `run_agent`, `QUEUE_INSTRUCTIONS` and its route, the old run API, the dashboard's to-do panel and queue-instructions section, and the to-do test in `e2e/queue.spec.ts`.

Success criteria:

- [x] Never more than N claims are worked at once: a test with a worker that counts how many are inside it at the same moment sees at most N for N of 1, 3 and 25.
- [x] A dispatch works every claim in progress and every waiting claim, oldest submitted first, and a claim in progress carries on from its saved step as the same attempt with one decision.
- [x] A claim that raises `ModelRateLimitError` once carries on as the same attempt, with one decision.
- [x] A claim that keeps raising it ends the dispatch with the claim still `in progress`, the other claims done, and the dispatch finished.
- [x] A claim that fails with another error is requeued and tried once more in the same dispatch, and a claim that fails twice is left for a handler. Neither stops the dispatch.
- [x] A claim another agent holds the lease on is skipped, and counted as done with a note.
- [x] No claim is decided or paid twice in any of these tests.
- [x] The queue agent, its tools, its instructions, the to-do list and `uv run -m agent` without a claim id are gone, and `uv run -m agent CLM-1001` still works one claim.
- [x] `agent/tests/test_structure.py` still passes, with checks added that only `dispatcher.py` imports `Send`, and that no module outside `agents.py` calls the claim graph.
- [x] `npm run check` is green.

Built as planned, with these differences: a dispatch also takes an approved claim a restart left unpaid (the old startup pass did, and the brief wants recovery after a restart); the worker's `decide` is a `Decide` protocol (`decide(claim_id, run_id=...)`) so tests pass a stand-in; the tag is `run-<id>`.

## Phase 3: starting a dispatch from the dashboard

- `backend/agent_service.py`: asks the agent's service to start a dispatch, and says so when the service can't be reached.
- `backend/main.py`: `start_dispatch` (N from 1 to 25), a thin call, with the 409 and 503 answers.
- `backend/runs.py`: the summary, built from the records with no model: how many claims were approved, declined and referred, each payout waiting for a sign-off, and each claim left for a handler or still in progress.
- `agent/service.py`: `POST /api/dispatches` answers at once or with a 409, creates the run through the backend, and works it in the background. When the service starts it marks unfinished runs stopped.
- `dashboard/src/api.ts`, `dashboard/src/types.ts`: the new calls and types, with cost converted in `api.ts` and nowhere else.
- `dashboard/src/components/StartDispatch.tsx`: N from 1 to 25, 3 to start with, and the start button.
- `dashboard/src/components/RunPanel.tsx`: each claim of the run and where it stands, the run's model cost and time, and the summary when it finishes. `QueuePage.tsx` uses both and keeps its totals.
- `e2e/agentStandIn.mjs`: also answers the start request and records N.

Success criteria:

- [x] A second start while a run is going is refused with a 409, and a start with the service down says "The agent's service isn't running".
- [x] The summary is built from the records: a test with known claims in each state checks every count and each payout waiting for sign-off.
- [x] The run panel shows the claims, the cost and the time, polling while the run is going.
- [x] An end-to-end test starts a dispatch on the queue page and the stand-in service sees N (checked for the default of 3 and for a changed N).
- [x] I check the queue page in the browser with the Playwright MCP server: the N chooser, the start, the panel and the 409 message. (Checked on a throwaway SQLite backend with the e2e stand-in: the chooser starts at 3, the start reached the stand-in with 3, and the panel listed the 25 claims as `to do` with cost and time. The 409 and 503 messages are covered by unit tests; the stand-in always answers 202.)
- [x] `npm run check` is green.

## Phase 4: evaluations

- `backend/seed_data.py`: reads `data/evals/` (the one place that does) into `held_out_claims` and `answer_key`.
- `backend/tables.py`: those two tables, and `evaluation_run_id` on `claims`.
- `backend/evaluations.py`: starts an evaluation. It copies the chosen set's claims (the five `tiny` ones, or all 25) under new ids and creates the run. One job: evaluation setup.
- `backend/claims.py`: the queue operations skip copies, `sign_off` refuses a copy, and `get_full` says whether a claim is a copy.
- `agent/dispatcher.py`, `agent/checkpoint.py`: for an evaluation a held approval counts as finished and the claim's saved progress is deleted.
- `agent/service.py`, `backend/agent_service.py`, `backend/main.py`: `start_evaluation`, with the set and N.
- `dashboard/src/components/PaymentPanel.tsx`: no sign-off form on a copy's page.
- `agent/tests/test_structure.py`: the answer key is read only by `seed_data.py`, `scoring.py`, `evaluations.py` and `runs.py`, never by `claims.py`, any agent module or any route that serves the agent.

Success criteria:

- [x] After an evaluation the queue is as it was: the same claims, the same counts per status, before and after.
- [x] A dispatch never carries on an evaluation's copies.
- [x] A held approval in a copy counts as finished, and its checkpoint is gone (a test with `InMemorySaver` shows no thread left).
- [x] Signing off a copy is a 409, and its page has no sign-off form.
- [x] `get_claim` on a copy holds nothing from the handlers' decisions: a test compares every value in the response against the answer key's decision, payout and reason.
- [x] The evaluation records its set, N, the model and the effort, and for each claim the decision, payout, reason, cost and time. (Kept in the copy's own records and the cost and time tables; Phase 5 reads them together.)
- [x] A run stopped partway shows as `stopped`, and its copies are never carried on.
- [x] `npm run check` is green.

Built as planned. The held-out claims' policies and customers were already seeded. `held_out_claims` and `answer_key` are read only by `tables.py`, `seed_data.py`, `evaluations.py` and (Phase 5) `scoring.py`; a structure test enforces it. The held approval's saved progress is cleared in `agents.decide_claim`, which holds the saver, not in `dispatcher.py` or `checkpoint.py`.

## Phase 5: the Scoreboard

- `backend/scoring.py`: the measures, pure, in `Decimal`.
- `backend/evaluations.py`: lists evaluations newest first with their measures, and opens one to its claims with the handler's decision and payout beside the agent's.
- `backend/main.py`: `list_evaluations` and `get_evaluation`, thin.
- `dashboard/src/pages/ScoreboardPage.tsx`: the start form (N, the set, whole or `tiny`) and the evaluations with every measure.
- `dashboard/src/pages/EvaluationPage.tsx`: the claims, the misses in Raspberry, each claim linked to its page.
- `dashboard/src/App.tsx`: the route and the nav link.

Success criteria:

- [ ] The measures match ones worked out by hand on a small set with a wrongful decline, a wrongful approval, a needless referral, a wrong amount and a claim the agent never decided (counted as a referral).
- [ ] Model cost per claim, time per claim and the run time are right for a run whose rows are known.
- [ ] An end-to-end test plays an evaluation out through the API, as the old run test did, and the scoreboard shows it with every measure; another starts an evaluation on the scoreboard and the stand-in service sees N and the set.
- [ ] I check the Scoreboard and an evaluation's page in the browser with the Playwright MCP server, including the misses and the links.
- [ ] `npm run check` is green.

## Phase 6: the docs and the live runs

- `docs/SPEC.md`: the sections on working the queue and on what the team needs to see. Its Rules are left alone.
- `docs/TECH_STACK.md`, `docs/STATUS.md`, `docs/PROCESS.md` (where these runs replace the five-claim cap), `docs/CODE_STANDARDS.md` (rules 10 and 13: the dispatcher is a fifth part of the agent, `agents.py` is the module that wires the claim agent, and the worker's `error_handler` is the one place an error is deliberately absorbed).

Success criteria, with one `npm run seed` first and `npm run dev` running on the default model, checked through the Playwright MCP server:

- [ ] Start a dispatch at N=3 and stop it partway with `kill -9` on every process listening on port 8002 (`lsof -ti tcp:8002`, which finds uvicorn's reloader and its worker), then start `npm run dev` again.
- [ ] A dispatch at N=25 then carries on the claims left in progress as the same attempts, and works the rest with 25 at once, which the claims' start times show. The run takes well under the sum of its claims' times.
- [ ] Claims worked from the start take about as long as at N=3. If they are slower, I report where the time goes, keeping to 4 connections.
- [ ] Claims held for sign-off wait, and a sign-off still pays within five seconds.
- [ ] No claim fails for want of a database connection, and during the dispatch Supabase shows no more than 12 connections whose user is `postgres` in `pg_stat_activity`, through the Supabase MCP server.
- [ ] An evaluation of the evaluation set at N=25, and one of the held-out set's five `tiny` claims at N=5, appear on the scoreboard with every measure, and the queue page's counts are the same before and after them.
- [ ] Through Langfuse's current API, the claims of the N=25 dispatch are found together by their tag. The older trace and score endpoints return a 410 for this project, so I use the observations API.
- [ ] `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/CODE_STANDARDS.md` and `docs/STATUS.md` describe the product as it now is.
- [ ] `npm run check` is green with `.env` moved out of the way, and the final diff passes the checklist in `docs/CODE_STANDARDS.md`.

## Decisions for you to check

- **Cost in billionths of a dollar.** A deliberate exception to the whole-cents rule for model costs. The alternative is a float, which rule 7 forbids.
- **`agents.py` as the brief's "harness".** `harness.py` stays generic.
- **Oldest first across both states.** The brief says "every claim left in progress and every waiting claim, oldest submitted first". I read that as one ordering by submission date, not in-progress claims first.
- **A claim skipped for a held lease counts as done**, with a note. Another agent is finishing it.
- **Copy ids are `EVAL-<run id>-<source id>`**, for example `EVAL-7-CLM-1203`.
- **No `carry_on` at startup.** A dispatch carries on claims in progress itself, so the old startup pass goes with the queue agent. A claim signed off while the service is down is paid by the next dispatch.

## Not in this plan

- Sign-off rejection, sign-in, real payments, messages to customers (`docs/SPEC.md`).
- Pointing the dispatcher at the agent in the cloud. The single function it calls is the seam for that later.
- Any change to the claim agent's graph, tools or instructions, apart from recording cost and time and the default model.
