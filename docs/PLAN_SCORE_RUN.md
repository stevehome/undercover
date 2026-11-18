# Plan: a `score_run` node for the dispatcher

The work is the Week 2 Day 4 challenge, done in `labs/week2day4 copy.ipynb`. It changes no product code: not `backend/`, `agent/` or `dashboard/`, and not `docs/` other than this plan.

## The problem

The dispatcher fans out with `Send`, one `work_claim` per claim, and then each branch goes straight to `END`. Nothing ever sees the whole run at once. Part 3 scores a run after the graph has finished, in notebook cells outside it. The challenge is to bring that scoring inside the graph: a `score_run` node after `work_claim` that scores the whole run and puts the scores in the state.

## Why this approach works

All the `Send`s from `fan_out` run in the same LangGraph step. A node that sits after `work_claim` starts in the next step, once every branch of the step before has finished and the `results` reducer (`operator.add`) has joined their lists. So a plain edge, `add_edge("work_claim", "score_run")`, is enough: `score_run` runs once, it sees every claim's result in `state["results"]`, and nothing else is needed to wait for the claims. A retried claim stays inside its own step, so retries don't make `score_run` run early or twice.

## What gets added, and where

Phases 1 and 2 were first built as a new section in `labs/week2day4 copy.ipynb`. That section depends on cells elsewhere in the lab, which is hard to run in the right order without paying for Part 2, so the finished version lives in a notebook of its own (see "A self-contained notebook" below). The copy is left as it is.

New cells go in a new section, "Your version: score_run", after the assignment box and before "Clearing out Langfuse". The existing cells stay as they are, so the lab still runs top to bottom. Each piece has one job:

- `Dispatch` gets a `scores` field: a dict with no reducer, because only `score_run` writes it. The existing `Dispatch` cell is not edited; the new section declares `ScoredDispatch(Dispatch)` with the extra field, so the lab's earlier graphs are unaffected.
- `score_run(state)`: builds the table from `state["results"]` with Part 3's `score_table` and `run_scores`, and returns `{"scores": {...}}` with each value as a plain `float`, so the state can be serialized (the stretch challenge's checkpointer needs that).
- `scored_stand_in(claim_id)`: a stand-in that returns the fields `score_table` needs (`decision`, `payout`, `rationale`, `cost`, `started`, `finished`). It copies the handler's decision from `labels` for every claim except one fixed claim, where it answers `refer`. This makes the correct scores known in advance, so the test is exact.
- `scored_dispatcher`: the graph `START -> list_claims -> work_claim (x N) -> score_run -> END`.

## Phase 1: `score_run` with the stand-in (no model, no cost)

Build `ScoredDispatch`, `score_run`, `scored_stand_in` and `scored_dispatcher`, and run it.

Success criteria:

- [x] `scored_dispatcher` draws with `score_run` after `work_claim`, and the cell after it shows the graph. (Checked the graph's nodes with `get_graph()`: start, list_claims, work_claim, score_run, end. I did not look at the rendered drawing.)
- [x] `result = scored_dispatcher.invoke({}, {"max_concurrency": 5})` returns a `scores` dict with the eight keys of `run_scores`, each a `float`.
- [x] `score_run` runs once. A counting wrapper around it records exactly one call at `max_concurrency` of 1, 5 and 25.
- [x] It runs after every claim finished. The wrapper sees 25 results on its one call, and `scores["accuracy"]` and `scores["decision_accuracy"]` equal 24/25 (0.96) for the one claim the stand-in gets wrong.
- [x] `scores["seconds"]` is at least 1 (each stand-in claim takes a second), and with 25 at once it is under 3. (Measured 5.02 s at 5 at once and 1.01 s at 25.)
- [x] With the flaky stand-in (CLM-1207 fails once, `RetryPolicy(max_attempts=3)`), `score_run` still runs once and still sees 25 results.
- [x] `result["scores"]` can be passed to `send_scores` unchanged (checked without Langfuse by looking at the dict, since the stand-in has no trace to score).
- [x] The behavior with no claims is checked and reported: with an empty `claims` the fan-out sends nothing, so I expect `score_run` not to run and `scores` to be absent or empty. The plan only records what happens; it does not add handling for it. (Result: with no claims, `score_run` does not run and the result has no `scores` key.)

## Phase 2: the real swarm, five claims

Swap `work_claim` (the lab's real node) into the same shape of graph, with `TINY = True` so it works 5 claims, as `docs/PROCESS.md` asks for live runs. This calls GPT-6 Luna through OpenRouter and costs a few cents; the free version of the lab, `labs/week2day4free.ipynb`, is the alternative.

Success criteria:

- [x] The graph with the real `work_claim` and `score_run` runs on 5 claims at `max_concurrency` 5 without error.
- [x] `result["scores"]` matches `run_scores(score_table(result["results"]))` computed outside the graph on the same results, key for key.
- [x] `send_scores(langfuse_handler.last_trace_id, result["scores"])` puts the scores on the run's trace, checked in Langfuse (the `Swarm` trace shows the eight scores). (Checked through Langfuse's v3 scores API, not the web page: all eight names have a score from the run's minute, with the run's exact values. The older trace and score endpoints return 410 for this account.)
- [x] `llm_cost` is above zero and `seconds` is below five times `seconds_per_claim`, which shows the claims overlapped.

Result of the live run (5 claims, 5 at once, GPT-6 Luna): accuracy 0.8, cost of mistakes $50, straight through 0.6, LLM cost $0.003, 27.9 seconds; one of the five answers was wrong.

## A self-contained notebook

`labs/week2day4_score_run.ipynb` holds the whole challenge and nothing else, so it runs top to bottom without the rest of the lab. It is tested in `labs/`, then copied and renamed into `community_contributions/steve_higgins/` for sharing. Whoever uses it copies it back into `labs/` first, so it keeps the lab's own `../data` paths and plain `week2day1_payout` import, and its introduction says to copy it into `labs/` before running. The copy of the original lab, `labs/week2day4 copy.ipynb`, is not changed.

The order of its cells, with the cost marked:

1. Introduction: the problem, and why a node after a fan-out is a join.
2. Setup (free): trimmed imports, the harder claims, policies and labels, the `Dispatch` state, `list_claims` and `fan_out`, and Part 3's scoring functions, copied from the lab.
3. Phase 1 (free): `ScoredDispatch`, `score_run`, the scored stand-in, the graph, the once-only check and the flaky retry check.
4. Phase 2 setup (free): the OpenRouter and Langfuse connection, the claim agent with its tools, `work_claim` and `send_scores`. Nothing here calls a model.
5. Phase 2 run (a few cents): the scored swarm on 5 claims, the check against scoring outside the graph, and the scores sent to Langfuse. A warning cell sits directly above it.
6. Wrap-up: a few lines on what changed and what to remember.

## Phase 3: the self-contained notebook

Build the notebook from the cells above, keeping the lab's own wording and code where it can be reused.

Success criteria:

- [x] Phase 1's checks pass when the notebook's free cells (steps 1 to 3) run from a restarted kernel, top to bottom, with no `.env` and no network. (Run with the OpenRouter and Langfuse keys removed from the environment.)
- [x] The whole notebook runs from a restarted kernel, top to bottom, without error. Only the step 5 swarm cell calls a model. (23 code cells, 0 errors, run with `nbclient` in a fresh kernel; the swarm cell cost about a third of a cent.)
- [x] The notebook uses the lab's own `../data` paths and plain imports, and runs from `labs/`.
- [x] Every code cell has its output cleared before any commit, as the git guide asks for shared notebooks.
- [x] `git status` shows only `labs/week2day4_score_run.ipynb` and this plan as new files. `labs/week2day4 copy.ipynb` is unchanged from before the notebook was built.

## Not in this plan

- The stretch challenge (compiling the dispatcher with `PostgresSaver`, restarting the kernel and resuming with `invoke(None, config)`). `score_run` returns plain floats so the state is ready for it.
- Any change to the product's backend, agent or dashboard. The lab says the product's dispatcher comes later, in `docs/SWARM.md`, which hasn't been copied into `docs/`.

## Open choices

- The stand-in copies the handlers' decisions from `labels`, which the notebook already loads from `data/evals/harder`. That is fine in a lab notebook. I have not opened those files while planning. It would not be allowed in the product, where the agent must never see them.
- I chose a subclass, `ScoredDispatch`, over editing `Dispatch`, so the lab's earlier cells keep working. If you would rather edit `Dispatch` in place, Phase 1 gets simpler but the earlier outputs no longer match the cells.

## running these changes
The new cells depend on some of the existing cells in the notebook.
When running the new ones, it is difficult to know which cells need to be run first before the ne additions.
Running all of the existing ones first would incur extra charges.

Would it be best to have the new functionality in a separate notebook or to make a copy of the required existing cells immediately in front of the new cells?
