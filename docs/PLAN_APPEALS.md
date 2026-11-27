# Plan: appeals to the ombudsman

Builds `docs/APPEALS.md` in six phases: the records and the documents (the tables, the eight starting appeals and the context layer's files), the app's logic and routes (recording, the check for hidden instructions, redress), the Copilot's tools and its pause before redress, the dashboard (the Appeals page and the claim page's panel), the documents and the guide's page, and the live checks. Nothing here creates or deletes anything on AWS. The deployed database and the context layer need a reseed and a redeploy afterwards, which you do.

## What I read

The brief, the seven documents `AGENTS.md` lists, `docs/COPILOT.md` and `docs/PLAN_COPILOT.md` for the plan's shape and the pause I reuse, and the code the appeals touch: `backend/payouts.py`, `claims.py` (the sign-off, the payment and `get_full`), `sent_back.py` (a kept history with a note, which appeals follow), `statuses.py`, `tables.py`, `needs_a_handler.py`, `over_limit.py`, `customers.py`, `reference.py`, `seed.py`, `seed_data.py`, `model_used.py`, `judge.py` (the app's one model call) and the routes in `main.py`; `agent/screening.py` and `agent/harness.py` (the claims' check and its model), `agent/copilot_confirm.py`, `copilot_tools.py`, and the Copilot's graph and context; the dashboard's `pages/`, `components/` and `api.ts`; `pyproject.toml`'s dependency groups; and `scripts/guide.ts`.

One thing to own up to: `docs/PROCESS.md` says not to open `data/evals/` unless asked. While answering your earlier question I opened `data/evals/ombudsman/` (the outcome counts in `sources.json`, the shape of `decisions.json` and `claims.json`, and the first lines of the label checklist). I haven't opened the two evaluation sets. Phase 1 opens the ombudsman folder again, because the brief says to draw the eight claims from it, and I'll open nothing else under `data/evals/`.

## Where I need your call

These are my choices where the brief leaves a gap or the code pulls another way. Tell me if you'd have them otherwise before I build.

1. **The check fails closed.** The app makes the model call for the hidden-instruction check when a handler records an appeal or an outcome. If the model can't be reached or gives no readable answer, the recording is refused with a 503 and nothing is saved, so no unchecked text gets in. The alternative, saving it as "unchecked", would let an unchecked text reach the Copilot.
2. **The check is the app's own module.** The claims' check lives in `agent/screening.py`, which needs LangChain, and the app's Lambda package (the `server` group) has none. `backend/appeal_check.py` asks the model through the `openrouter` package, as `judge.py` does, with instructions of its own about an appeal's two texts, on the same model and effort as the claims' check, honoring `MODEL_NAME`. The tests answer it from the stand-in on `OPENROUTER_ORIGIN`, as the judge's are answered.
3. **A second read for models.** The dashboard needs a marked appeal's text, and the Copilot must never see it. They sign in the same way, so the app can't tell them apart by who is asking. I add two reads for the Copilot, under `/api/copilot/appeals`, which leave out a marked appeal's two texts, and keep the dashboard's reads whole. A test checks the Copilot's tools never call the whole ones.
4. **The claim agent never sees an appeal.** `GET /api/claims/{id}` is open to the agent's key, so it stays as it is, with one new key, `customer_appeals`: a line for each appeal on that customer's claims, with the claim, the outcome and the date. The claim page reads its appeal from a handlers-only route.
5. **The appeals section of the claims manual is section 15,** added at the end, so no existing section number moves. The other changes go in sections 3, 9, 11, 12, 13 and 14 as the brief says. The wording's complaints section is added as the last section, and the wording goes to 2026.2 with the cover sections unchanged, so the manual's line "everything here applies to claims under wording version 2026.1" becomes 2026.1 and 2026.2.
6. **The eight claims are numbered CLM-16xx,** which no file in `data/` uses. A test checks no claim id is shared across the queue, the evaluation sets, the ombudsman cases and these eight. They live in `data/appeals/`: `claims.json` (each with its decision, payout, calculation and payment), `policies.json`, `customers.json` and `appeals.json`, so the seed never reads `data/evals/`.
7. **The Copilot's pause serves both payments.** `agent/copilot_confirm.py` gains a second card kind, `redress`, rather than a second node, since the pause, the answer and the check in code are the same. The graph's edge after the model sends either call to it.
8. **The third handover question needs a claim with no appeal,** and all eight have one. So after the guide's capture run (which works the whole queue), the live check records an appeal on a claim the agent declined, whichever that run gave. It costs nothing extra.

## Design

- **An appeal has two tables.** `appeals` holds the appeal, its outcome, its three redress amounts and the check's result and cost, with a unique key on the claim, so a second appeal is refused by the database. `redress_payments` holds the payment, with the claim's id as its primary key too, so a second payment is refused by the database as well. An appeal's identity is its claim's id, since a claim has at most one, so the routes take a claim id and there are no appeal ids. Nothing is written to `claims`: the decision and the claim's own payment stay as they were, and `over_limit.py`'s count of claims paid over the limit is unchanged.
- **The status is read, not stored twice.** An appeal is `with the ombudsman` until it has an outcome, then `upheld` or `not upheld`. Whether redress is waiting or paid is whether a row exists in `redress_payments`. The claim's label (`appeal open`, `appeal upheld, redress waiting`, and so on) is worked out in one function.
- **Check, then write.** Recording takes the model's answer first, with no database connection held, then writes in one `db.connection()`, as `backend/tests/test_connections.py` requires. The check runs on the text being recorded: the grounds for an appeal, the reason for an outcome. A text that has an instruction marks the appeal, with the check's reason, and costs are added to the appeal's.
- **Redress is a handler who can sign off, at any amount,** through the same dependency the sign-off route uses. The amount paid is read from the appeal's own row; the request has no amount to change.
- **The Copilot's confirmation card is read from our records,** never from what the model wrote, as the sign-off's is: the claim, the customer, the three amounts and the ombudsman's reason, with the reason left out of a marked appeal's card.
- **The seed doesn't touch what a dispatch works.** The eight are decided, so a dispatch ignores them. The queue's waiting count stays 26 and its decided count starts at 8.
- **The tests that count the queue change in Phase 1,** where the counts change, and not later.

## Phase 1: The records and the documents

The database holds appeals and their redress, the seed loads eight claims with their appeals, and the context layer's files carry the complaints rules at new versions.

- `backend/statuses.py`: `AppealStatus` (with the ombudsman, upheld, not upheld).
- `backend/tables.py`: `appeals` and `redress_payments`, as in the design.
- `data/appeals/claims.json`, `policies.json`, `customers.json` and `appeals.json`: made from the ombudsman cases, with a decision record on each claim that section 14 of the manual would accept, a payment where it was approved and, for any payment over the approval limit, a senior handler's sign-off. Two appeals open, three upheld (one with its redress paid, two waiting) and three not upheld, each consistent with its claim. `data/README.md` lists the folder.
- `backend/appeal_seed.py`: reads that folder into rows for the claims, policies, customers, appeals and redress payments, with amounts in cents.
- `backend/seed_data.py`: `records()` includes them.
- `context/policy_wording.md`, `claims_manual.md`, `claim_rules.yaml`, `glossary.yaml` and `data_dictionary.yaml`: the changes in section 10 of the brief, at new versions and review dates, with the claims manual's new appeals section as section 15.
- Tests that count the queue (backend, agent and e2e fixtures) change to the new counts.

**Success criteria**

- [x] `uv run pytest backend -q` passes, adding `test_appeal_seed.py`: after a seed the queue has 34 claims, 26 waiting and 8 decided; there are eight appeals, two with the ombudsman, three upheld and three not upheld; one upheld appeal has a redress payment and two don't.
- [x] Each of the eight claims passes the decision-record checks in `backend/decision_record.py`, and the count of claims paid over the limit equals the count with a handler's sign-off, as `over_limit.get()` reads them.
- [x] Each upheld appeal's three amounts are zero or more and together more than zero; a not upheld appeal has none; a test shows the database refuses a second appeal for a claim and a second redress payment for an appeal.
- [x] The 26 waiting claims, `held_out_claims` and `answer_key` (25 and 50 rows) are as they were, and no claim id is shared between the queue, the two sets, the ombudsman cases and the eight.
- [x] `npm run check:context` passes. The wording and the manual are at their new versions, the manual still has sections 1 to 14 as they were and a section 15, and the context layer's lookups find `appeal`, `redress` and `final response` in the glossary and the complaints section in a search of the documents.
- [x] `uv run pytest -q`, ruff and pyright pass; `docs/STATUS.md` is updated; committed.

## Phase 2: Appeals in the app

A handler can record an appeal and an outcome, a senior handler can pay redress, the app checks the text, and the reads the dashboard and the Copilot need are served.

- `backend/appeal_check.py`: asks the model whether a text tries to instruct whoever handles the appeal, and returns what it found, its reason and its cost; refuses with a 503 when it can't get a readable answer.
- `backend/model_used.py`: `for_appeal_check()`.
- `backend/appeals.py`: the appeals' state and its one home in the database: record an appeal (the claim must have a final decision, approved and paid or declined, and not be an evaluation's claim; one for each claim), record an outcome (only on an open appeal, with the redress when upheld), read one, list them, and the one-line history for a customer.
- `backend/redress.py`: pay redress once, by a handler who can sign off, from the appeal's own amounts, in one conditional write.
- `backend/appeal_figures.py`: the counts and sums on the Appeals page, worked out in code.
- `backend/appeal_view.py`: the appeal as the dashboard reads it, and as a model reads it, which leaves out a marked appeal's grounds and reason.
- `backend/appeal_routes.py`: an `APIRouter` that `main.py` includes. Recording an appeal, recording an outcome (each takes any signed-in handler), paying redress (a senior handler), and the reads: the list with the figures, an appeal, a claim's appeal, and the two for the Copilot. Each has an `operation_id` and a one-line docstring, and none takes the agent's key.
- `backend/claims.py`: `get_full` adds `customer_appeals`.
- `backend/needs_a_handler.py`: two more groups, appeals waiting for an outcome and redress waiting for a sign-off.
- `docs/SPEC.md`: the payment rule's wording, the feature list and the Appeals page.

**Success criteria**

- [x] `uv run pytest backend -q` passes, through the API with the sign-in helper and the check answered by the stand-in:
  - an appeal is recorded on a decided claim; refused on a claim that is waiting, in progress, held, sent back, referred or an evaluation's; and refused when the claim has one already
  - an outcome is recorded on an open appeal only; an upheld one needs its amounts and a not upheld one takes none
  - a handler who can't sign off is refused redress, with the reason, and a senior handler pays it once with their name and the time; the amount is the recorded three, a second payment is refused, and the claim's own payment is untouched
  - a marked appeal is saved with its reason and the check's cost; a failed check is a 503 and saves nothing
- [x] A test asks every new route with no credentials, with the agent's key alone, and with a handler's, and only a handler's works; `GET /api/agent/openapi.json` has exactly the operations it has today.
- [x] `get_claim` with the agent's key has `customer_appeals` as one line each and holds no appeal's grounds or reason, with a marked and an unmarked appeal on the customer's claims; the Copilot's two reads leave out a marked appeal's texts and keep an unmarked appeal's.
- [x] The tests' autouse connection guard (`backend/tests/conftest.py`) fails any request that holds two connections, and every recording and payment test runs under it.
- [x] The Appeals figures (open, upheld, not upheld, the upheld share, redress paid and waiting) match the records, with none decided as a case; a structure test says only `appeals.py` and `appeal_view.py` read the grounds and reason columns.
- [x] `uv run pytest -q`, ruff and pyright pass; `docs/SPEC.md` and `docs/STATUS.md` are updated; committed.

## Phase 3: The Copilot

The Copilot can look up appeals, record them and their outcomes, and pay redress after the handler confirms.

- `agent/copilot_api.py`: the calls to the new routes, with the handler's sign-in.
- `agent/copilot_appeal_tools.py`: `list_appeals`, `get_appeal`, `record_appeal`, `record_appeal_outcome` and `pay_redress`, at module level, the last refusing without the confirmation the pause records, as `sign_off_claim` does. `agent/copilot_tools.py` lists them.
- `agent/copilot_confirm.py`: the pause serves `sign_off_claim` and `pay_redress`, with a second card kind, `redress`, read from our records.
- `agent/copilot_graph.py` and `copilot_state.py`: the edge after the model sends either call to the pause, and the state says which call was confirmed.
- `agent/copilot_instructions.py`: what appeals are and what it may do with them, as a goal, with no steps.

**Success criteria**

- [ ] `uv run pytest agent -q` passes with a stub model and the real backend through `TestClient`:
  - the reads, the two recordings and a refusal passed on with its reason
  - the pause before redress, answered by a freshly built Copilot on the same saved state: nothing is paid before the answer, Cancel pays nothing, and the answer pays once
  - a handler who can't sign off gets no card
  - the card's amounts and reason come from our records, not the call's arguments, and a marked appeal's card has no reason
  - no tool result holds a marked appeal's grounds or reason
- [ ] `agent/tests/test_structure.py` passes: no `copilot_*` module imports the agent's key, `send` or `api`, and none calls the dashboard's whole appeal reads.
- [ ] `what_needs_a_handler` answers with the two new groups.
- [ ] `uv run pytest -q`, ruff and pyright pass; `npm run check:runtime` passes; `docs/STATUS.md` is updated; committed.

## Phase 4: The dashboard

Handlers can see, record and pay appeals on the dashboard, and the Copilot's sidebar shows the redress card.

- `dashboard/src/types.ts` and `api.ts`: the appeal types and calls, with amounts converted at `api.ts` only.
- `dashboard/src/pages/AppealsPage.tsx`: the figures, the filter by status and the list, each row linking to its claim; the empty state.
- `dashboard/src/components/AppealPanel.tsx`: the panel on the claim page, below the decision, with the label.
- `RecordAppealForm.tsx`, `RecordOutcomeForm.tsx`, `PayRedress.tsx` (through `ConfirmDialog`): the three actions; a handler who can't pay sees what they can't do and why.
- `ConfirmationCard.tsx`: the redress card.
- `Navigation.tsx`, `App.tsx`, `pages/ClaimPage.tsx`, `StatusPill.tsx`, `theme.css`: the route, the nav entry beside the Scoreboard, the panel and the label, following `docs/BRAND.md`.
- `e2e/appeals.spec.ts`, `e2e/judgeStandIn.mjs` (answers the appeal check, marking a text that tells the AI to approve) and `e2e/copilotStandIn.mjs`: the scripted turns.

**Success criteria**

- [ ] `npm run check:ts` passes with 80% coverage: component tests for each form's validation, the three outcomes' panels, the label in each state, the figures, the filter, the empty page, the can't-do message, and the redress card's two buttons.
- [ ] `npm run e2e` passes, adding the Appeals spec (the page's figures and rows; recording an appeal and an outcome on a claim; paying redress; Marcus sees why he can't; a marked appeal shows its reason) and the Copilot spec's redress card, and every existing spec passes with the new counts.
- [ ] Checked in the browser with the Playwright MCP server, in light and dark and on a narrow window: the Appeals page, a claim with each appeal state, and the redress card; the fonts and colors match `docs/BRAND.md`, with no one-edge borders or gradients.
- [ ] `npm run check` is green with `.env` moved out of the way; `docs/STATUS.md` is updated; committed.

## Phase 5: The documents and the guide's page

The documents describe the product as it now is, and the guide has an Appeals section ready for its pictures.

- `docs/SPEC.md`, `docs/TECH_STACK.md` (the tables, the routes, the check and the two Copilot reads), `docs/CODE_STANDARDS.md` (the check's one home and who may read an appeal's texts), `docs/PROCESS.md` if it names anything that changed, `docs/STATUS.md` and `data/README.md`.
- `guide/index.html`: an Appeals section and a picture of a claim with an appeal, with alt text, in light and dark, on the grey placeholders until Phase 6.
- `scripts/guide.ts` and `scripts/guide/`: the two new pictures, `appeals` and `claim-appeal`, taken from the seed before the dispatch.

**Success criteria**

- [ ] `uv run pytest backend/tests/test_guide.py -q` passes with the new section: every picture has alt text, a file and its pair.
- [ ] `npm run check:ts` passes on the script, and `npm run guide` is still not part of `npm run check`.
- [ ] The documents name each new module's job, and `agent/tests/test_structure.py` and `eslint.config.js` hold any rule I added.
- [ ] `docs/STATUS.md` says how to run the appeals work and what to redeploy; committed.

## Phase 6: The live checks

After one reseed, with `npm run dev` on the default model. I'll ask you to run `npm run seed` with `npm run dev` stopped, then start it again.

- [ ] 1: `npm run guide` takes every picture, the appeals ones included, and I look at each in both themes for cut-off text, a token, an `.env` value or an AWS identifier.
- [ ] 2: Signed in as Dana Whitfield, the Appeals page shows the eight appeals in their five states and its figures match the records.
- [ ] 3: "What appeals do we have, and how many has the ombudsman upheld?" answers from our records, and agrees with the Appeals page.
- [ ] 4: "Pay the redress on CLM-..., the one waiting." shows the redress card with the claim, the customer, the three amounts and the reason; nothing is paid until Sign off and pay; then it is paid once with Dana's name and the time on the claim's page. A reload before answering keeps the card.
- [ ] 5: "Record an appeal on CLM-..." on a claim the agent declined in the guide's run, then the ombudsman's decision on it, as upheld with redress and as not upheld on another declined claim, with the real model checking each text.
- [ ] 6: An appeal whose grounds tell the AI to approve in full is recorded and marked with the check's reason, and the Copilot is shown only that it is marked.
- [ ] 7: Signed in as Marcus Oyelaran, "pay the redress on CLM-..." is declined with the reason and no card.
- [ ] 8: No response, log, step or table holds a sign-in token (the same search as the Copilot's).
- [ ] 9: I report what the runs spent. By the guide's runs, a dispatch is about $0.04 and the Copilot's turns half a cent; the check adds a fraction of a cent for each text.
- [ ] 10: `npm run check` is green, and the whole change is reviewed against the checklist in `docs/CODE_STANDARDS.md`, including the code outside the appeals the build touched.

## Not for now

What the brief lists: the agent deciding, preparing or predicting appeals, learning from upheld appeals, letters, a second appeal, withdrawing one, changing a recorded outcome, a time limit the app enforces and bulk import. I also leave a Copilot suggestion button for appeals, and an appeals column on the queue page.

## What you do afterwards

Nothing I build changes what's deployed. To see appeals on AWS: reseed the deployed database (the tables are new, and the seed drops the schema), redeploy the app's Lambda, and redeploy the context layer so its new files and versions are served. `agentcore deploy` only if the Copilot's package changed, which it will have, for its tools.

I stop here, with no code written, until you ask me to implement the plan.
