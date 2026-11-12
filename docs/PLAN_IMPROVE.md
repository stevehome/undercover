# Plan: an improver, versions of the claim agent, and handlers who sign in

Builds `docs/IMPROVE.md`: handlers sign in with Supabase Auth, the claim agent's instructions, model and reasoning effort become versions, a judge (Jev) grades each explanation, an improver agent proposes changes that a handler approves and that code keeps or rolls back, a Settings page, and a dashboard that looks like enterprise software.

SIDENOTE: For consistency with the course, please read `labs/week2day5.ipynb` and build the judge, the configuration's versions and the improver in the same style as the lab. Where the lab and this brief differ, follow the brief.

I have read the lab. It gives the shapes I build on:

- **The judge:** `judge(rationale, decision, expected)` calls Jev with a state of the handler's decision, reason and reference beside the agent's decision and rationale, and three questions: a `score` question over the grades F, C, B and A (score 0 to 3, letter the most likely level) and two `noul` questions, `same_grounds` and `same_section`.
- **The configuration:** a dict of instructions, model and reasoning effort, kept in a list of versions, with `make_agent(config)`.
- **The scoring:** `is_right`, `mistake_cost` and `run_scores`, with the grade added; averages of a version's runs on a set; `compare` and `keep_or_roll_back` against `OBJECTIVES`, `NOISE` and `TOLERANCE`.
- **The improver:** `create_agent` on Luna at medium effort, with `HumanInTheLoopMiddleware` on `propose_change` and `propose_recipe`, four tools named `read_results`, `propose_change`, `run_evaluation` and `propose_recipe`, a recipe as its instructions, one Langfuse session for the improver's traces, and `difflib.unified_diff` to show what a proposal changes.
- **The setup at the end:** the handlers as Supabase users, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` and `HANDLER_PASSWORD` in `.env`, sign-ups off, the keys at `/auth/v1/.well-known/jwks.json`, and a credit limit on the OpenRouter key.

Where the lab and the brief differ I follow the brief:

- The lab keeps everything in memory (`versions`, `rounds`, `scoreboard`, `recorded`). Here the backend owns every record, and a restart or a wait for a handler loses nothing.
- The lab's improver runs on an `InMemorySaver` and sees the held-out set through the same process. Here it has a `PostgresSaver` of its own, and what it reads comes from the backend's `improver_view`, which holds the held-out set's scores only.
- The lab's `run_evaluation` runs the claims in its own process and judges them in the notebook. Here the agent's service works them through the dispatcher and the backend grades them as it finishes each evaluation.
- The lab's budget is one number in code. Here the spending limit is a setting, each round works to a copy of the settings as they stood when it started, and a round can't start a claim once it has spent its limit.
- The lab's `propose_change` saves a version straight away. Here a proposal is a record that changes nothing until a handler approves it, and a proposal outside the models allowed never reaches a handler.

## What I found in the code

Places where the brief's notes on the last build don't match this build. I follow the brief's intent.

- **The one-run rule is a database index, not a lock.** The brief says a `threading.Lock` in `agent/service.py`. In this build, the partial unique index `one_running_run` on `runs.status = 'running'` is the rule, and the 409 comes from the backend. I keep that and extend it (see "One thing at a time" below), so a round's stretch of work is a run too.
- **There is no `SignOffForm.tsx`.** The sign-off form is in `PaymentPanel.tsx`, and `sign_off_claim` takes a `handler_id` today.
- **`data/handlers.json` already has each handler's email,** but the `handlers` table has no email column, and all three handlers have `can_approve_over_limit: true`. Seeding adds the column, and Marcus Oyelaran and Priya Raman become `false`.
- **The claim agent's instructions are a Python constant** (`CLAIM_INSTRUCTIONS` in `backend/instructions.py`), not a file. The brief says seeding makes version 1 from "the instructions file", with the recipe in a file beside it. I move the text to `data/claim_instructions.md` and put the recipe in `data/improver_recipe.md`, and `seed_data.py` reads both. `backend/instructions.py` and `GET /api/claim-instructions` go, with the Instructions page.
- **The styles file is `dashboard/src/theme.css`,** not `styles.css`. Its dark mode comes from `prefers-color-scheme` alone.
- **There is no `dashboard/package.json`.** The dashboard's dependencies are in the root `package.json`, so `@supabase/supabase-js` is added there.
- **`openrouter` and `pyjwt[crypto]` are already in `pyproject.toml`.** I check with `uv sync` that both resolve, and add nothing if they do.
- **No reasoning effort is recorded as `none`** (`harness.NO_EFFORT`), and Luna also has a real level called `none`. The brief wants `default`, so the constant and the tests that name it change.
- **`ModelSettings` comes from `MODEL_NAME` today,** and the service records it on the run. With versions, the claim agent's model comes from the run's version, and `MODEL_NAME` makes the one model allowed.
- **The structure tests need new homes:** `test_structure.py` lists who may read `answer_key` and who may import `httpx`, `Send` and the graph builders. The judge, the improver's view and the improver's client are added to those lists, and a check keeps the claim agent's client from reaching the scores.
- **Rule numbers:** the brief says rules 7 and 13 of `CODE_STANDARDS.md` cover the improver's client and the dashboard's Supabase client. In this repo it's rule 9 (every outside call has one home) and rule 10 (the harness and the tools), and I update those, with rule 7 for the judge's cost.

## Design

**Sign-in.** The dashboard signs in through `dashboard/src/auth.ts`, the one module that imports `@supabase/supabase-js`, and `api.ts` sends the access token with each action. The backend (`backend/auth.py`) checks it with PyJWT's `PyJWKClient` against `<VITE_SUPABASE_URL>/auth/v1/.well-known/jwks.json` with the audience `authenticated`, finds the handler by the token's email, and gives routes two dependencies: `signed_in_handler` and `senior_handler` (can sign off over the limit). `backend/errors.py` gets `Unauthorized` and `Forbidden`, turned into 401 and 403 in the one place that already turns `NotFound` and `Conflict` into 404 and 409. Reads stay open, because the agent reads the same routes until Week 3's API key. Every action a handler takes is checked: sign-off, dispatch, evaluation, start or stop a round, approve or reject a proposal, change a setting. A new `GET /api/me` returns the signed-in handler, so the header and the pages know what they can't do.

**Configuration and recipe versions.** Two tables, `configurations` (version, instructions, model, reasoning effort) and `recipes` (version, text), each with the reason, who proposed it, who approved it and when, and the round it came from. Version 1 of each is seeded. A configuration has a `verdict` (`kept` or `rolled back`, null until its round decides; version 1 is `kept`), and the current version is the highest `kept` one, derived from the rows so it can't drift from a separate pointer. `runs` gets `configuration_version`. A dispatch and a Scoreboard evaluation record the current version, and an evaluation in a round records the version under test. The claim agent fetches its version through two operations, one for a run and one for no run (`uv run -m agent CLM-1001` and a claim resumed after a sign-off), and neither returns scores. `backend/diffs.py` turns two texts into diff lines with `difflib`, which the API returns as lines with a kind (added, removed, context) so the dashboard only colors them.

**The scores of a version** (`backend/version_scores.py`) are the averages of the measures of the whole-set evaluations that rounds ran on it: `runs` with a `round_id` and `tiny = false`. An evaluation started on the Scoreboard counts for nothing here. A grade of none is left out of the average, and a set with no graded claim at all has no grade. The current version needs one run on the evaluation set and two on the held-out set; a round runs whatever is missing first.

**The judge.** `backend/judge.py` holds the one call to Jev, through OpenRouter's Decisions endpoint with the `openrouter` package and the lab's three questions. It passes `server_url` on each call, read once from the environment (`OPENROUTER_ORIGIN`, defaulting to `https://openrouter.ai`), because the client ignores an address set on it. Seeding adds each label's `reason` and `reference` to `answer_key`. `backend/grading.py` grades an evaluation's claims in parallel as part of finishing it, each call timing out after 10 seconds with the SDK's retries off, so finishing stays under 20 seconds against the agent's 30-second wait on the backend. A claim the agent didn't decide gets an F with no call, a claim the judge couldn't grade is stored as not graded, and each grade keeps the probabilities of the two checks and the call's cost. The letter is the level with the highest probability, never the score rounded. With `MODEL_NAME` set, the judge isn't called.

**Rounds** (`rounds`, `proposals`, `improver_calls`). A round is one improver run with a stage: first evaluations (1, 2 or 3 of 3), improver working, change waiting, evaluations (1, 2 or 3 of 3), verdict, recipe waiting, finished or stopped. It records the recipe version it followed, a snapshot of the improvement settings, the version tried, the improver's reason, the held-out scores before and after, the verdict and why, and who started it and when. Each proposal is a row in `proposals` (kind, the proposed content, the reason, pending, approved or rejected, who decided and when, a rejection's reason), which is the ledger of what a handler approved. The improver's model calls are rows in `improver_calls`, with OpenRouter's `usage.cost` in billionths as for the claim agent. A round's cost is those, plus the model cost of its evaluations' claims, plus the judge's cost.

**One thing at a time.** The rule stays a unique index on running runs, with two changes. A new run kind, `improver`, is a stretch of the improver's work: the first evaluations, the improver working and the evaluations after an approval. The evaluations inside a stretch are runs too, with `parent_run_id` set, and the index applies only to running runs with no parent, so a round's evaluations are never refused because of the stretch they belong to. While a round waits for a handler no stretch is running, so a dispatch or an evaluation can run. An approval or rejection begins a new stretch, and so is refused with a 409 naming what is running, before anything is recorded. Please check this choice: it keeps the rule in the database where the swarm put it, instead of adding a lock in the service as the brief's notes describe.

**The spending limit** (`backend/spending.py`). A round's spent money is the improver's calls, all of the round's evaluations and the judge. The estimate for an evaluation is its claims times the highest cost per claim seen so far for its model, or for a model with no runs yet the current model's cost scaled by the larger of the ratios of the two models' input and output prices. The dispatcher's worker asks the backend before it starts a claim whether the claim's round has spent its limit, and a round that has stopped answers no too. An evaluation with claims left unstarted finishes as `stopped`, and a version whose evaluations were stopped, or that the round can't afford to evaluate, is rolled back. Claims already in flight finish, so a round can overshoot by what those cost.

**The verdict** (`backend/verdict.py`). Pure `Decimal` functions with the lab's rule and the brief's: the new version's held-out average against the current version's scores, accuracy and grade compared as differences, cost and time as fractions of the old value, with the floors on accuracy and the grade. It is kept when it meets the objectives, at least one measure improves by more than its noise, and none gets worse by more than its tolerance. A version with no grade is rolled back.

**The improver** is `agent/improver.py`: a LangChain `create_agent` on GPT-6 Luna at medium effort, with `parallel_tool_calls` off in its model settings, a cap on its model calls for each round as the claim agent has, and `HumanInTheLoopMiddleware` on the two propose tools. Its instructions wrap the recipe, written as goals: what the claim agent works from, and that a change never names a claim. A small middleware checks a proposal's model and effort against the models allowed before the human-in-the-loop pause, so a bad one goes back to the improver as a tool message and never reaches a handler (I confirm the middleware order with a test). A second small middleware ends the improver's run when its round is stopped. Its tools are in `agent/improver_tools.py`, with the lab's four names, reading their state from `ToolRuntime[ImproverContext]` (round id). They reach the backend only through `agent/improver_api.py`; both clients share one backend-call helper in `agent/backend_http.py`, since two modules must not share a helper through a third that isn't about it. `run_evaluation` works the evaluations in the agent's service through the dispatcher inside a fresh `contextvars.Context`, as the harness does for each claim graph. Its checkpointer is a `PostgresSaver` of its own from `checkpoint.py` (the only module that talks to Postgres), saving with `durability="sync"`, and each round has a new thread id. `agent/rounds.py` runs a round's stretches: it starts one, waits through a pause, resumes it with the handler's decision, and stops it. The service records the decision and the handler through the backend before it resumes the improver, and the backend records nothing of its own on an approval or a rejection. A restart marks the stretches that were running as stopped, and a round stopped before its verdict leaves the current version as it was; one stopped after its verdict keeps it.

**Settings** are rows in the `settings` table the backend already has, seeded from `data/company.json` for the approval limit and from a new `data/improvement.json` for the rest (the objectives, noise, tolerance, spending limit and agents at once, with the lab's values and 25). `backend/platform_settings.py` reads and changes them, validating each value and recording who changed it and when in `setting_changes`. Every part of the product reads them from there, and a new approval limit applies to the decisions recorded after it. The models allowed are in `data/models.json` (name, reasoning efforts, price per million input and output tokens as numbers), seeded into a table and read only. With `MODEL_NAME` set, the one model allowed is that model at effort `default` and a price of 0. The appearance is the one setting the browser keeps.

**The dashboard.** New shared pieces: a page header, a navigation that marks where you are, a status pill (color and word), a table style that right-aligns numbers with their units, a diff view, a confirmation dialog built on `<dialog>`, loading, empty and error states, and a version chart in plain SVG. Dark mode becomes an attribute on the page (`data-theme`) with the system choice as the default. Polling updates data in place and keeps the last data on screen, so nothing jumps.

**The tests use stand-ins.** The end-to-end tests run a stand-in for Supabase Auth (`e2e/authStandIn.mjs`: signs tokens with its own key, serves the public keys and answers the cross-origin checks) and one for the judge (`e2e/judgeStandIn.mjs`), beside the agent's stand-in. Backend tests sign tokens with a key of their own and point the key client at it through a dependency. Vite reads the root `.env` for `npm run dev` only (`envDir` set by mode in `dashboard/vite.config.ts`), and the unit and end-to-end tests set their own values, which win over any file.

## Before the live runs (the student's part)

The lab's "Setting up for the product": the three handlers made as users in Supabase Auth with sign-ups off, `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` and `HANDLER_PASSWORD` in `.env`, and a credit limit on the OpenRouter key. I check the sign-ins in Phase 1 with the lab's three checks, before building on them. Reseeding needs `npm run dev` stopped, and I ask you to run `npm run seed` as before, since the agent may not.

## Phase 1: sign-in

- `backend/auth.py`: verify the token and find the handler; the two dependencies. One job: who is signed in and what they may do.
- `backend/errors.py` and `backend/main.py`: `Unauthorized` and `Forbidden` become 401 and 403 in one place. The actions that need a handler take the dependency, and `sign_off_claim` loses its `handler_id` input. `GET /api/me`.
- `backend/tables.py`, `backend/seed_data.py`, `data/handlers.json`: `email` on `handlers`, and `can_approve_over_limit` false for Marcus Oyelaran and Priya Raman.
- `dashboard/src/auth.ts`: the Supabase client, sign in, sign out and the session's token. `api.ts` sends the token, and a 401 sends the page to sign in.
- `dashboard/src/pages/SignInPage.tsx`; `App.tsx` guards every other page and shows the signed-in handler with a sign-out in the header; `PaymentPanel.tsx` signs off as the signed-in handler, and says why when a handler can't.
- `dashboard/vite.config.ts`: `envDir` by mode. `e2e/authStandIn.mjs`, `e2e/signIn.ts` and `playwright.config.ts`: the stand-in and a helper every spec uses.
- `pyproject.toml`/`package.json`: `@supabase/supabase-js` added; the Python packages confirmed.

Success criteria:

- [x] I run the lab's three checks against the real project (sign-ups off, each handler signs in, a public key is served), and report the result. Result: sign-ups are off (`signup_disabled`), all three handlers sign in, and a public key (ES256) is served. The password has a `#`, so I quoted it in `.env`: Node's env loader read it as a comment.
- [x] A test signs tokens with a key of its own: a valid token is accepted, and a missing, malformed, badly signed, wrong-audience, expired or unknown-email token is refused with 401.
- [x] Every action a handler takes (sign-off, dispatch, evaluation) is refused without a valid sign-in, and still works with one. The agent's own routes under `/api/runs` and the reads stay open.
- [x] A sign-off over the limit by Marcus Oyelaran is refused with 403 and a reason, and by Dana Whitfield it records Dana as the signer; `sign_off_claim` takes no `handler_id`.
- [x] `GET /api/me` returns the signed-in handler with whether they can sign off over the limit.
- [x] Dashboard tests: the sign-in page signs in and shows a wrong password's message; a page without a session goes to sign-in; the header shows the handler's name and signing out returns to sign-in; the token goes with each action.
- [x] Every end-to-end spec signs in through the stand-in, and `npm run check` passes with `.env` moved away.
- [x] With the Playwright MCP server I sign in as Dana Whitfield on the real Supabase project and open the queue, and the backend accepts the token (checked by a `GET /api/me` through the dashboard). Done with a Playwright script that reads the password from `.env`, to keep it out of the transcript: Dana signs in, `/api/me` answers 200 and the header shows her name.
- [x] `npm run check` is green.

## Phase 2: the Settings page

- `data/improvement.json` and `data/models.json`: the starting values (the lab's objectives, noise, tolerance and a spending limit of $0.50, with 25 agents at once) and the three models allowed with their efforts and prices.
- `backend/tables.py`, `backend/seed_data.py`: `setting_changes` and `models`, and the settings rows seeded from the two files and `company.json`.
- `backend/platform_settings.py`: read the settings, change one (validated, with who and when), list the models allowed. One job: the platform's settings. `payouts.py` reads the approval limit from here.
- `backend/main.py`: `list_settings`, `change_setting` (senior only) and `list_models`, thin.
- `dashboard/src/pages/SettingsPage.tsx`: every handler sees the settings and the models allowed; a senior handler edits, with a confirmation dialog. `dashboard/src/theme.ts` and `theme.css`: light, dark or the system's, remembered by the browser, with the colors set from an attribute as well as `prefers-color-scheme`.
- `dashboard/src/components/ConfirmDialog.tsx`: the dashboard's own dialog.

Success criteria:

- [x] A new approval limit applies to the next decision: with the limit raised, an approval that waited for sign-off before is paid straight through, and the claims decided before keep their state.
- [x] A change is recorded with the handler and the time, a value out of range is refused, and Marcus Oyelaran's change is refused with 403 while Dana Whitfield's succeeds.
- [x] The models allowed can't be changed through any operation, and with `MODEL_NAME` set the one model allowed is that one at effort `default` and price 0.
- [x] The page shows what a handler who can't change settings can't do and why, and has no edit controls for them.
- [x] Switching the appearance changes the page's colors in both directions and each browser remembers it (a unit test and an end-to-end test).
- [x] I check the page in the browser as Dana and as Marcus (Playwright MCP) in light and dark mode.
- [x] `npm run check` is green.

## Phase 3: the configuration's versions

- `data/claim_instructions.md`, `data/improver_recipe.md`: version 1 of each (the claim agent's instructions as they are today, and the lab's recipe). `backend/instructions.py` and its route go.
- `backend/tables.py`, `backend/seed_data.py`: `configurations` and `recipes` with version 1, `runs.configuration_version`.
- `backend/versions.py`: create, read, the current version, listing. One job: versions of the configuration and recipe.
- `backend/diffs.py`: two texts into diff lines with `difflib`. One job: diffs.
- `backend/runs.py`, `backend/evaluations.py`: a dispatch and an evaluation record the current version, and an evaluation takes a version to test when it has one.
- `backend/main.py`: `get_current_configuration`, `get_run_configuration` (neither holds scores), `list_configurations`, `get_configuration_diff`, `list_recipes`.
- `agent/harness.py`: `model(settings)` builds the model from a version; `NO_EFFORT` becomes `default`. `agent/api.py`: fetch the version. `agent/agents.py`: build the claim agent from the run's version (the current one when there is no run).
- `dashboard/src/pages/ConfigurationPage.tsx` replaces `InstructionsPage.tsx`: the current version and every version, with what any version changed from the one before as a diff (`DiffView.tsx`).

Success criteria:

- [x] After a seed, version 1 of the configuration is the claim agent's instructions with `openai/gpt-6-luna` at `low`, and version 1 of the recipe is the lab's recipe.
- [x] A dispatch and an evaluation each record the version they used, and with a newer kept version they record that one; an evaluation given a version to test records it.
- [x] A claim worked with a stub model uses the version's instructions and model (checked on the stub's captured request), and a claim worked with no run uses the current version.
- [x] The operation the claim agent uses to fetch its version returns no scores (checked on its response model).
- [x] The diff operation matches `difflib` on known texts, with additions and removals marked.
- [x] `MODEL_NAME` still wins: the run records that name with effort `default`, and the existing tests that named `none` are updated.
- [ ] `uv run -m agent CLM-1001` with `MODEL_NAME=openrouter/free` after a reseed works one claim, and I report what it decided. **Deferred to the live runs in Phase 8**, so the database is reseeded once, not twice (the new tables need a reseed on Supabase). **Tried twice and not ticked:** `openrouter/free` sent `calculate_payout` line kinds such as "accommodation" that the tool refuses, and the claim graph only turns `ApiRefusal` into a tool message, so the run raised; that is the same in HEAD. The default model is what the rest of the live checks used.
- [x] I check the Configuration page in the browser (Playwright MCP).
- [x] `npm run check` is green.

## Phase 4: the judge

- `backend/tables.py`, `backend/seed_data.py`: `reason` and `reference` on `answer_key` (read from `data/evals/` by seeding, as the brief allows), and `claim_grades`.
- `backend/judge.py`: the one call to Jev, and the letter from the probabilities. One job: asking the judge.
- `backend/grading.py`: grade an evaluation's claims in parallel, store the grades and their cost. One job: grading an evaluation.
- `backend/runs.py`: `finish_run` grades an evaluation's claims before it finishes.
- `backend/scoring.py`: `grade` (average, none when no claim is graded) and the judge's cost, added to the measures.
- Dashboard: `types.ts`, `api.ts` and `measures.ts` carry the grade; `ScoreboardPage.tsx` adds the average grade; `EvaluationPage.tsx` shows each claim's letter and score and the two checks as yes or no, and the judge's cost beside the model's.
- `e2e/judgeStandIn.mjs`; `agent/tests/test_structure.py` allows `judge.py`, `grading.py` to read `answer_key` and still keeps it from every claim operation.

Success criteria:

- [x] The letter is the level with the highest probability: a test with probabilities whose score would round to a different letter gets the most likely one.
- [x] A claim the agent didn't decide gets an F and the stub judge is not called for it; a claim the judge fails on is not graded and is left out of the average; a run with no graded claim has no grade.
- [x] A test with a stub judge that sleeps for a second per call grades 25 claims in a few seconds (parallel), and the calls pass `server_url`, a 10-second timeout and retries off.
- [x] The judge's cost is on the evaluation, apart from the claim agent's, and the scoreboard shows the average grade beside the other measures.
- [x] With `MODEL_NAME` set, the judge isn't called and claims show as not graded.
- [x] The structure test shows no module outside the readers opens `answer_key`, and the reasons never appear in a claim operation's response.
- [x] An evaluation on the five `tiny` claims of the evaluation set with the default model and the real judge: I report the grades, checks and cost, and look at three by hand against the handler's reason. Run 1 (GPT-6 Luna, low effort): 4 of 5 decisions right, grade 1.184 (four Cs, one F), cost $0.004273 plus $0.000146 for the judge. By hand: CLM-1007 and CLM-1015 give the handler's grounds (damage under the per-item limit and deductible; an accidentally left child is not a covered reason); CLM-1020 is the one wrong, the agent declined for no police report where the handler accepted the guide's letter, and its F is deserved.
- [x] `npm run check` is green.

## Phase 5: rounds in the backend

- `backend/tables.py`: `rounds`, `proposals`, `improver_calls`, `runs.round_id` and `runs.parent_run_id`, and the unique index limited to runs with no parent.
- `backend/statuses.py`: the round stages and the new run kind.
- `backend/version_scores.py`: a version's scores from its rounds' whole-set evaluations, and the needs of the current version.
- `backend/verdict.py`: the keep or roll back rule.
- `backend/spending.py`: spent, left, the estimate, and whether a claim may start.
- `backend/improver_view.py`: what `read_results` returns: the current version and its scores on both sets; from the latest evaluation on the evaluation set the wrong claims and the five right ones explained least well, with the handlers' decisions and reasons, the agent's, the grade and the two checks; the earlier rounds; the objectives, noise, tolerance and rule; what is left of the spending limit; the models allowed. From the held-out set, scores only.
- `backend/rounds.py` and `backend/proposals.py`: a round's records, a proposal's checks and decision, the verdict, stopping. These raise `NotFound`, `Conflict`, `Forbidden`.
- `backend/agent_service.py`: asks the service to start a round, stop one, or resume one with a decision, and passes on a refusal.
- `backend/main.py`: handler operations `start_round`, `stop_round`, `decide_proposal` (all senior only, through the service) and `list_rounds`, `get_round`, `get_proposal`; service operations `get_improver_view`, `record_improver_call`, `record_proposal`, `record_round_stage`, `record_verdict`, `may_start_claim`.
- `agent/api.py` gains `may_start_claim` for the dispatcher and nothing else about rounds.

Success criteria:

- [x] A version kept and one rolled back by the rule, with the measures worked out by hand: cost and time as fractions of the old value, accuracy and the grade as differences; a version with no grade is rolled back.
- [x] A version's scores count only the whole-set evaluations its rounds ran (Scoreboard evaluations and tiny ones are left out).
- [x] The improver's view holds nothing from the held-out set but its scores: a test searches the view for every held-out claim's id, reason and reference.
- [x] A proposal changes nothing until it is approved: no version or recipe exists before, and the approver is recorded after.
- [x] A proposal outside the models allowed is refused with a reason and is never `pending`; a rejection records the handler's reason.
- [x] An approval while a dispatch runs is refused with a 409 that names the dispatch, with nothing recorded; a round's evaluations are never refused because of its own stretch.
- [x] An evaluation estimated to cost more than what is left is refused, a round that has spent its limit gets no new claim, and the evaluation cut short ends `stopped`; its version is rolled back.
- [x] A stopped round leaves the current version as it was when stopped before the verdict and keeps it when stopped after, and the backend refuses what a stopped round records.
- [x] A round keeps the settings it started with when they change, and the verdict, the spending limit and the estimate use that copy.
- [x] Start, stop and decide are refused with 403 for Marcus Oyelaran and 401 without a sign-in, and a start while a run is going is a 409.
- [x] A round's cost is the improver's calls, its evaluations' claims and the judge, summed from the records.
- [x] `npm run check` is green.

## Phase 6: the improver

- `agent/improver.py`: build the improver from a recipe. One job: the improver agent.
- `agent/improver_tools.py`: the four tools. `agent/contexts.py`: `ImproverContext`.
- `agent/improver_api.py` and `agent/backend_http.py`: the improver's client and the shared call plumbing. `agent/api.py` is reduced to the claim agent's calls on the same helper.
- `agent/checkpoint.py`: the improver's saver, with `durability="sync"`.
- `agent/rounds.py`: a round's stretches (start, pause, resume with a decision, stop) and its first evaluations. `agent/service.py`: `POST /api/rounds`, `POST /api/rounds/{id}/stop` and `POST /api/rounds/{id}/decision`; the lifespan stops unfinished stretches.
- `agent/harness.py`: model settings for the improver (medium effort, parallel tool calls off, a cap on its calls for each round).
- `agent/tracing.py`: the improver's session, named after the round, and tags `round-<id>` and `run-<id>` on the claims of its evaluations.
- `agent/dispatcher.py`: the worker asks `may_start_claim` before a claim.

Success criteria:

- [x] With a scripted stub model, a round carries out the recipe: the first evaluations when the current version lacks them, the improver's proposal pausing the round, an approval creating the new version, `run_evaluation` working once on the evaluation set and twice on the held-out set, the verdict recorded, and a recipe proposal pausing the round again.
- [x] A rejection's reason reaches the improver as the tool's reply, and the improver may propose again.
- [x] A proposal naming a model or effort that isn't allowed goes back to the improver as a tool message and never reaches a handler.
- [x] A round waiting for approval survives a restart: a new process with the same thread resumes it.
- [x] A round stopped by a handler starts no more claims or model calls and lets go of the one-run rule when the work in hand ends; a restart marks the round stopped.
- [x] A claim graph's thread is its own when `run_evaluation` runs inside the improver (a test of the fresh `contextvars.Context`).
- [x] The improver's model settings have `parallel_tool_calls` off, and its model calls are capped; a test hits the cap.
- [x] The claim agent's client still can't reach the scores or the handlers' decisions (`test_the_agent_cant_read_the_scoreboard`, extended), `improver_api.py` is the only other module that makes backend calls, and only `dispatcher.py` imports `Send`.
- [x] With `MODEL_NAME` set, the improver and the claim agent use that model; the structure tests pass.
- [x] `npm run check` is green.

## Phase 7: the Improvement page

- `dashboard/src/pages/ImprovementPage.tsx`: start a round, stop an open one (with confirmation), where the round has got to as it happens, the proposal waiting with its diff, the rounds so far newest first, the chart and the recipe's versions.
- `dashboard/src/components/RoundProgress.tsx`: the stage and the n of 3 counts. `ProposalReview.tsx`: the instructions' diff, the model and effort before and after, and approve or reject with a reason, each behind the confirmation dialog. `RoundsTable.tsx`. `VersionChart.tsx`: the held-out accuracy and grade of each version tried, in SVG with no new library. `DiffView.tsx` shared with the Configuration page, which now also shows every version's held-out scores.
- `dashboard/src/api.ts`, `types.ts`: the round operations and types, with cost converted in `api.ts` only.
- `e2e/improvement.spec.ts`: signs in, plays out a round through the API with a proposal waiting, approves it, changes a setting and switches the theme. `e2e/agentStandIn.mjs` records the round calls and the handler.

Success criteria:

- [x] The page shows each stage as it happens (tested with a round moved through every stage through the API): first evaluations 1, 2 and 3 of 3, the improver working, a change waiting, the evaluations 1, 2 and 3 of 3, the verdict, a recipe waiting, and finished or stopped.
- [x] A proposal waiting shows the instructions' diff with additions and removals in color and the model and reasoning effort before and after, and approve or reject sends the handler's decision (and the rejection's reason) to the agent's service, behind the dashboard's own dialog.
- [x] A handler who can't approve sees what they can't do and why, with no buttons; a 409 or 503 from the backend shows its reason.
- [x] The rounds show newest first with the recipe version, the settings, the version tried, the reason, the held-out scores before and after, the verdict and why, who approved or rejected, and the cost; a round that proposed nothing shows no version tried.
- [x] The chart plots each version tried and has a table of the same numbers for a reader who can't see it.
- [x] The Configuration page shows each version's held-out scores and any version's diff from the one before.
- [x] The end-to-end tests sign in, approve a proposal played out through the API, change a setting and switch the theme.
- [x] I check the page with the Playwright MCP server against a seeded SQLite backend with the stand-ins, in light and dark mode.
- [x] `npm run check` is green.

## Phase 8: the look of the whole dashboard, the documents and the live runs

- `dashboard/src/components/PageHeader.tsx`, `Navigation.tsx`, `StatusPill.tsx`, `DataTable.tsx`, `EmptyState.tsx` and `theme.css`: the same header and spacing on every page, navigation showing where you are, tables that line up with numbers right-aligned and units in the headings, statuses in a color and a word, buttons that look alike, and loading, empty and error states that say what to do next. The existing pages (queue, claim, scoreboard, evaluation) move to them with no change in how they work. Everything follows `docs/BRAND.md` in both modes and fits a laptop screen.
- `usePolling.ts` and the pages: updates in place, no layout shifts.
- Documents: `docs/SPEC.md` (the approval limit is a setting; the improver reads the evaluation set's decisions and reasons while the claim agent never sees them and nothing reads the held-out set's; sign-in, the improver and what the team needs to see), `docs/TECH_STACK.md`, `docs/PROCESS.md`, `docs/CODE_STANDARDS.md` (rules 9 and 10 for the improver, its client and the dashboard's Supabase client, rule 7 for the judge's cost), `docs/STATUS.md` and `data/README.md`.

Success criteria:

- [x] Each existing page and the new ones share the header, spacing and navigation, with numbers right-aligned in tables and statuses as a color and a word; the existing end-to-end tests pass unchanged apart from signing in.
- [x] Polling a page that has data never empties it or moves the content (checked with a long-running round on the Improvement page).
- [x] After one `npm run seed` (which I ask you to run), with `npm run dev` and the default model, signed in as Dana Whitfield through a Playwright script (not the MCP server, to keep the password out of the transcript): two rounds from the Improvement page, rejecting the first proposal with a reason and approving the next and the rest. Round 1: the first change was rejected with a reason; the next became version 2 (held-out accuracy 86.0% to 90.0%, grade 1.450 to 1.489), rolled back because seconds per claim got worse; its recipe was approved (cost $0.147). Round 2 (id 5): version 3 and a recipe approved; rolled back on time per claim, 926 s, which the backend stall below caused (cost $0.067). The page lagged the backend by 10 to 20 s, which led to the polling fix.
- [x] Through Langfuse's API, each round's improver traces are found in one session, and the evaluations' claims by their round and run tags. Through the v2 observations API (the old sessions and traces endpoints are deprecated): session `round-1` holds 4 traces (one per stretch of the improver's work) and `round-5` holds 3; the tag `run-19` finds 35 claim traces (25 claims, with retries) and `round-5` finds the round's evaluation claims.
- [x] I report how far version 1's two held-out runs differed on each measure, beside the noise and the tolerance. Runs 7 and 8: accuracy 0.88 and 0.84 (0.04 apart; noise 0.10), grade 1.480 and 1.420 (0.06; noise 0.15), cost per claim $0.000882 and $0.000950 (7.2%; noise 15%), seconds per claim 40.5 and 46.3 (14.4%; noise 15%, so only just inside).
- [x] A dispatch at N=25 on the current version runs. Signed in as Marcus Oyelaran, a payout waiting for sign-off can't be signed off and the settings can't be changed; signed in as Dana Whitfield, the same payout is signed off and paid within five seconds. Run 21 (before a second reseed) ran all 25 claims at once ($0.024), and Marcus was refused a sign-off and a settings change with 403. After the reseed, Dana lowered the limit to $300, and dispatch run 1 at 25 left nine payouts waiting; Marcus was refused on CLM-1001 (403), Dana signed it off at 08:52:20.085 and the $420.00 was paid at 08:52:21.973, 1.9 s later (checked in the database). The limit is back at $1,000.
- [x] Screenshots of every page in light and dark mode at a laptop width. A fresh subagent reviews them once, as a senior product designer would, against `docs/BRAND.md` and point 8 of the brief, and I fix what it finds.
- [x] I report what the live checks spent, which should come to under $1 on GPT-6 Luna, and what the OpenRouter key's usage shows. The database records about $0.44 (evaluations $0.206, dispatch $0.024, improver rounds $0.214, judge extra); the OpenRouter key shows $0.243 for today and $1.39 in all, of a $10 limit.
- [x] The documents above describe the product as it now is.
- [x] `npm run check` is green with `.env` moved out of the way, and I report the results.

## What I need from you

- Please check the design choices flagged above: a round's stretch of work as a run kind with `parent_run_id` on its evaluations (instead of the lock in the service that the brief's notes describe), the instructions and recipe moved to files in `data/`, and `NO_EFFORT` renamed from `none` to `default`.
- The Supabase setup and the three `.env` lines from the lab, and a credit limit on your OpenRouter key, before Phase 1's live check.
- Reseeding before the live runs in Phase 8, with `npm run dev` stopped.

## Feedback

The Scoreboard tab content doesn't fit completely the right side is truncated.

This error occurred after approving an improver change
discarding closed connection: <psycopg.Connection [BAD] at 0x1278a1700>
[agent] Round 1 failed
[agent] Traceback (most recent call last):
[agent]   File "/Users/steve/projects/undercover/agent/rounds.py", line 127, in work_stretch
[agent]     _improve(round_id, run_id, resume, llm, saver)
[agent]   File "/Users/steve/projects/undercover/agent/rounds.py", line 100, in _improve
[agent]     result = graph.invoke(start, config, context=context, durability="sync")
[agent]              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/langgraph/pregel/main.py", line 4000, in invoke
[agent]     for chunk in self.stream(
[agent]                  ^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/langgraph/pregel/main.py", line 2988, in stream
[agent]     with SyncPregelLoop(
[agent]          ^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/langgraph/pregel/_loop.py", line 1870, in __enter__
[agent]     saved = self.checkpointer.get_tuple(self.checkpoint_config)
[agent]             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/langgraph/checkpoint/postgres/__init__.py", line 238, in get_tuple
[agent]     cur.execute(
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/psycopg/cursor.py", line 117, in execute
[agent]     raise ex.with_traceback(None)
[agent] psycopg.OperationalError: consuming input failed: server closed the connection unexpectedly
[agent]         This probably means the server terminated abnormally
[agent]         before or while processing the request.
[agent] server closed the connection unexpectedly
[agent]         This probably means the server terminated abnormally
[agent]         before or while processing the request.
[backend] INFO:     127.0.0.1:58996 - "POST /api/improver/rounds/1/stage HTTP/1.1" 200 OK
[backend] INFO:     127.0.0.1:59028 - "GET /api/configurations HTTP/1.1" 200 OK
[backend] INFO:     127.0.0.1:59095 - "GET /api/rounds HTTP/1.1" 200 OK
[backend] INFO:     127.0.0.1:58996 - "POST /api/runs/7/finish HTTP/1.1" 200 OK
[agent] ERROR:    Exception in ASGI application
[agent] Traceback (most recent call last):
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/uvicorn/protocols/http/h11_impl.py", line 411, in run_asgi
[agent]     result = await app(  # type: ignore[func-returns-value]
[agent]              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/uvicorn/middleware/proxy_headers.py", line 63, in __call__
[agent]     return await self.app(scope, receive, send)
[agent]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/fastapi/applications.py", line 1163, in __call__
[agent]     await super().__call__(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/applications.py", line 96, in __call__
[agent]     await self.middleware_stack(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/middleware/errors.py", line 186, in __call__
[agent]     raise exc
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/middleware/errors.py", line 164, in __call__
[agent]     await self.app(scope, receive, _send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/middleware/exceptions.py", line 63, in __call__
[agent]     await wrap_app_handling_exceptions(self.app, conn)(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
[agent]     raise exc
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
[agent]     await app(scope, receive, sender)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/fastapi/middleware/asyncexitstack.py", line 18, in __call__
[agent]     await self.app(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/routing.py", line 676, in __call__
[agent]     await self.middleware_stack(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 2734, in app
[agent]     await route.handle(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 1281, in handle
[agent]     await super().handle(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/routing.py", line 282, in handle
[agent]     await self.app(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 158, in app
[agent]     await wrap_app_handling_exceptions(app, request)(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 53, in wrapped_app
[agent]     raise exc
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/_exception_handler.py", line 42, in wrapped_app
[agent]     await app(scope, receive, sender)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/fastapi/routing.py", line 145, in app
[agent]     await response(scope, receive, send)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/responses.py", line 172, in __call__
[agent]     await self.background()
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/background.py", line 36, in __call__
[agent]     await task()
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/background.py", line 23, in __call__
[agent]     await run_in_threadpool(self.func, *self.args, **self.kwargs)
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/starlette/concurrency.py", line 34, in run_in_threadpool
[agent]     return await anyio.to_thread.run_sync(func)
[agent]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/anyio/to_thread.py", line 65, in run_sync
[agent]     return await get_async_backend().run_sync_in_worker_thread(
[agent]            ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 2706, in run_sync_in_worker_thread
[agent]     return await future
[agent]            ^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/anyio/_backends/_asyncio.py", line 1100, in run
[agent]     result = context.run(func, *args)
[agent]              ^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/agent/rounds.py", line 127, in work_stretch
[agent]     _improve(round_id, run_id, resume, llm, saver)
[agent]   File "/Users/steve/projects/undercover/agent/rounds.py", line 100, in _improve
[agent]     result = graph.invoke(start, config, context=context, durability="sync")
[agent]              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/langgraph/pregel/main.py", line 4000, in invoke
[agent]     for chunk in self.stream(
[agent]                  ^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/langgraph/pregel/main.py", line 2988, in stream
[agent]     with SyncPregelLoop(
[agent]          ^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/langgraph/pregel/_loop.py", line 1870, in __enter__
[agent]     saved = self.checkpointer.get_tuple(self.checkpoint_config)
[agent]             ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/langgraph/checkpoint/postgres/__init__.py", line 238, in get_tuple
[agent]     cur.execute(
[agent]   File "/Users/steve/projects/undercover/.venv/lib/python3.12/site-packages/psycopg/cursor.py", line 117, in execute
[agent]     raise ex.with_traceback(None)
[agent] psycopg.OperationalError: consuming input failed: server closed the connection unexpectedly
[agent]         This probably means the server terminated abnormally
[agent]         before or while processing the request.
[agent] server closed the connection unexpectedly
[agent]         This probably means the server terminated abnormally
[agent]         before or while processing the request.


### What I changed for this feedback

- **Scoreboard cut off on the right:** its 13 columns, with headings that never wrapped, came to 1,487 px inside a 1,136 px panel. Headings now wrap, the Scoreboard's panel is wider (up to 1,600 px, with a 1 rem gutter) and data tables use slightly tighter side padding. The table now fits with no sideways scroll at 1,280, 1,366 and 1,440 px.
- **Round failed after approving a change (`server closed the connection unexpectedly` in `get_tuple`):** the improver waits for a handler with the database connection idle, the database closes idle connections, and the agent's pool in `agent/checkpoint.py` handed the resumed round a dead one. The pool now tests a connection before handing it out (`check=ConnectionPool.check_connection`), with a test that it is built that way. This is the agent's counterpart of the backend's `pool_pre_ping`. `npm run dev:agent` has no `--reload`, so the agent needs a restart to pick it up. A round that had already failed stays stopped; start a new one.

The Scoreboard now has a **Round** column: the round that started an evaluation, or "–" for one started by hand. The backend already sent `round_id`. The extra column needed the table's side padding trimmed again (0.5rem); it still fits with no sideways scroll at 1,280, 1,366 and 1,440 px.
