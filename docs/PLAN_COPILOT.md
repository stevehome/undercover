# Plan: the UnderCover Copilot

Builds `docs/COPILOT.md` in six phases: the app's side (a handler's conversations, their turns and steps, the reads the Copilot needs), the Copilot's loop with its reads and actions, the pause before a sign-off with the wait for the agent's work and the success criteria, the Copilot as an AgentCore app with its deployment files, the sidebar, and the live checks. Nothing here creates anything on AWS: the Copilot's runtime, its Memory and the Gateway are covered by stand-ins and tests, and your deployment notebook makes the real ones.

SIDENOTE: For consistency with the course, please build the Copilot the way the course has built its agents. Its agent loop is a LangGraph `StateGraph` written by hand: a node that calls the model, LangGraph's `ToolNode`, and the loop between them, with a `PostgresSaver` checkpointer, as in `labs/week2day3.ipynb` and the claim agent's graph. Please don't use LangChain's `create_agent` for it. The pause before a sign-off is an `interrupt()` in a node of its own, resumed with `Command(resume=...)`, since LangGraph runs an interrupted node again from the top when it resumes, as the claim agent's wait for a handler is a node of its own. The handler's sign-in reaches the graph and its tools in the graph's context (`context_schema`, read through `ToolRuntime`), never in the config, whose values LangGraph saves with each checkpoint. The Copilot is an AgentCore app of its own, made with `BedrockAgentCoreApp`, with one entrypoint and each turn's work registered as an async task, as the claim agent's AgentCore app does, and it is synchronous throughout, as the claim agent is. `labs/week3day4_lab1.ipynb` and `labs/undercoverlab/` show a pause in one Runtime session resumed in another. Its memory is `AgentCoreMemoryStore` as a LangGraph store, as the claim agent's memory is, with the Memory itself made as in `labs/week3day3.ipynb`. It reaches the context layer over MCP with `MultiServerMCPClient`, as in `labs/week2day2.ipynb`, and through the Gateway as in `labs/week3day2_lab2.ipynb` and `labs/week3day3.ipynb`. `labs/week3day4_lab2.ipynb` deploys the claim agent and points the app at it, and `labs/week3day5_lab1.ipynb` deploys the Copilot beside it, so please match the names that notebook uses. Read these notebooks without running them. Where a notebook and this document differ, follow this document. Include this sidenote in your plan too.

## What I read

The brief, the seven documents `AGENTS.md` lists, `docs/PLAN_RUNTIME.md` for the plan's shape, and the code the Copilot reuses: the claim agent's graph, nodes, state, context, tools, step recording, memory, credentials, readiness, background work, operations, entrypoint and checkpointer; the backend's sign-in, access rules, agent service, Runtime route, starts, statuses and the routes in `main.py`; the dashboard's shell, polling and the end-to-end setup; and `agentcore/` and `runtime/`.

From the notebooks, I read `labs/week3day5_lab1.ipynb` whole, and in the others only the cells that bear on the Copilot's shape: `week3day4_lab1.ipynb` and its small agent in `labs/undercoverlab/app/agent/main.py` (a graph that pauses in one session and resumes in another from its checkpoints in Supabase, answering `__interrupt__` in the state), and the `MultiServerMCPClient` cells of `week2day2.ipynb` and `week3day2_lab2.ipynb`. I did not go through `week3day3.ipynb`'s memory cells; the claim agent's `agent/memory.py` is the memory code I follow. Day 5's notebook fixes the names, and I use them as they are:

- the runtime is `copilot` in `agentcore/agentcore.json`, deployed as `undercover_default_copilot`, beside `agent`
- the settings are `UNDERCOVER_COPILOT_MEMORY_ID` (on the runtime) and `UNDERCOVER_COPILOT_RUNTIME` (on the app); on the laptop, `UNDERCOVER_COPILOT`, default `http://127.0.0.1:8081`
- the Memory is `undercover_copilot_memory`, with a User Preference strategy on `/handlers/{actorId}/preferences/` and a Semantic one on `/handlers/{actorId}/facts/`
- the runtime health check is `{"operation": "health"}`, answered `{"healthy": true}`, and the runtime's file is `runtime/copilot.py`
- the notebook says CLI 1.0.0-rc.5; this project's CLI is rc.7 with the CDK package pinned at 1.0.0-rc.4, as `NOTES.md` records. Nothing here depends on the difference.

## Where I need your call

These are my choices where the brief and the code pull different ways. Tell me if you'd have them otherwise before I build.

1. **MCP: `MultiServerMCPClient` or the claim agent's `McpConnection`.** The sidenote says `MultiServerMCPClient`, and the brief says the Copilot is synchronous throughout. The two don't meet: `MultiServerMCPClient` makes async-only tools, and a synchronous `ToolNode` can't call them. That is why the claim agent has `agent/mcp_connection.py`, one place that runs each MCP call on an event loop of its own. I plan to use the claim agent's seven context tools and its `McpConnection` (and `GatewayRoute`, for the signing) as they are, since the brief says to reuse the claim agent's code where it fits, and to say so in `docs/TECH_STACK.md`. If you want `MultiServerMCPClient`, the cost is an async wrapper around each call, written once.
2. **Flat modules named `copilot_*.py` in `agent/`,** as the improver's are `improver_*.py`. The structure tests (`agent/tests/test_structure.py`) look at `agent/*.py`, so a subfolder would escape them.
3. **Markdown in the sidebar needs a library.** The dashboard has none. I'd add `react-markdown` and `remark-gfm` (for the small tables). `react-markdown` never renders raw HTML, which matters for text a model wrote. Icons are small inline SVGs, with no icon package.
4. **A turn whose sign-in is refused at its very start can't report it.** Reporting it to our app takes the same sign-in. It ends with no model call, as the brief says, and our app's 20-minute rule then shows it as stopped. This should only happen to a sign-in that expired between the app's own check and the Copilot's, since the dashboard renews it first.
5. **One new read the brief implies: what needs a handler.** The brief says what it is (payouts held for sign-off, claims referred or left for a handler, and sent-back claims the agent hasn't worked). The dispatch summary has some of these. I add one read for all three, so the answer is counted by our app and not by the model. If Phase 1 finds the summary already holds all three, I use it and drop the read.
6. **The app names the Copilot's model** and sends it in each turn's payload (`backend/model_used.py`, `for_copilot()`, which honors `MODEL_NAME`), as it names the claim agent's and the improver's. The Copilot reads it from the payload.
7. **Another handler's conversation is a 403,** with a message saying it belongs to someone else. A conversation id is a random identifier, so this tells no one anything.

## Design

- **The app holds the conversation's record; Supabase holds its state.** The sidebar reads the app: messages, steps, where the turn stands and the confirmation card. The Copilot's LangGraph checkpoints, in the same database and schema as the claim agent's, hold what the model needs. `npm run seed` drops the schema, so both go.
- **The conversation's id is its thread and its Runtime session.** `copilot-<uuid4>`, 44 characters of letters, digits and hyphens, which Runtime and the Memory both accept.
- **One turn at a time, decided by a conditional `UPDATE`,** as a sign-off is. A turn begins only when the conversation isn't working (or has been working for over 20 minutes, and so shows as stopped); the handler's message is saved in the same transaction.
- **A turn stopped partway can be carried on.** A new message on a thread whose last reply asked for tools nobody answered would be refused by the model's API. The turn driver first answers each unanswered tool call with "That step didn't finish", then adds the handler's message.
- **The sign-in goes through, never into storage.** The dashboard sends it to the app as it sends it everywhere. The app checks it, then puts it in the payload to the Copilot (`sign_in`). The Copilot keeps it only in the graph's context, which isn't checkpointed, and in the header of each call to our app. The context field is `repr=False`, nothing logs a payload, and a test searches every table, every checkpoint and every recorded step for the token.
- **The agent's key never reaches the Copilot's calls.** `agent/backend_http.py`'s `send` is split in two: `request` (the one HTTP client and its 429 retry, taking the headers) and `send` (adds the agent's key). Only `copilot_api.py` calls `request`, with the sign-in. A structure test says no `copilot_*` module imports the key's name, `send`, `api` or `direct`.
- **A route that only reads the context layer.** The Copilot's route to the context layer is the Gateway's with only the context target on Runtime, or a direct MCP call to the context layer without the app on the laptop. `copilot_route.py` wraps either and refuses the app target, so a tool can't reach the app's tools "as the agent" even by mistake.
- **A pause in a node of its own, with only reads before it.** The `confirm` node reads the claim and customer from our records, checks in code that the handler may sign off, and calls `interrupt()` with the card. Nothing is written before the pause, since the node runs again from the top on resume. The turn driver, outside the graph, tells the app it is waiting once the graph has returned its interrupt.
- **Waiting is a function, not the model.** `copilot_waiting.py` polls one run every few seconds through a read a handler may use, and stops at 15 minutes. `start_dispatch` and `start_evaluation` take a `wait` the model sets when the handler wants the outcome, and `check_success_criteria` always waits. A blocked tool keeps its card "working" with its seconds, which is what the sidebar should show.
- **Figures come from code.** `copilot_criteria.py` is pure `Decimal` functions: the three criteria, their targets, their figures and whether each is met. The 70% target is a named constant; the accuracy target is the `objective_accuracy` setting; the third figure is two counts from our app. The tool returns them and the model writes the answer around them.
- **The labeled sets' decisions stay out.** The Copilot reads evaluations through `backend/copilot_view.py`, which gives their measures and costs and no claim's handler decision, as `improver_view.py` does for the improver. A structure test lists who may touch the answer key, as for the improver.
- **Memory is on only when its setting is there.** With `UNDERCOVER_COPILOT_MEMORY_ID` unset the recall and save nodes do nothing, and the card for the lookup doesn't appear.
- **Both runtimes are one package.** `cdk-stack.ts` stages `runtime/` and `agent/` once for every runtime in the stack, so the Copilot needs only `runtime/copilot.py`, an entry in `agentcore.json` and its own role policy. The Copilot's Memory has a different name from the claim agent's (`undercover_copilot_memory-*` against `undercover_memory-*`), so the claim agent's `policy.json` doesn't cover it and the Copilot gets a policy file of its own.

## Phase 1: The app's side

The app keeps a handler's conversations, one turn at a time, with the steps and the confirmation card, asks the Copilot to work a turn, and serves the reads the Copilot needs. The Copilot isn't built yet: tests use a stand-in that records the payloads it is sent and calls the app back as the real one will.

- `backend/tables.py`: `copilot_conversations` (id, handler, title, created, the turn's status and when it started, the waiting card, the failure's reason), `copilot_messages` (the handler's and the Copilot's, with an answer's calls, cost and seconds) and `copilot_steps` (tool, kind, input, state, times, a trimmed result, files with sources, a reason).
- `backend/statuses.py`: `TurnStatus` (working, waiting for a confirmation, done, failed), `StepState` (working, done, refused, failed) and `CardKind` (claims, customers, context, agent work, memory, action).
- `backend/copilot_conversations.py`: make, list (a handler's own, newest first, titled by the first question) and read a conversation; the one place that says whose it is.
- `backend/copilot_turns.py`: begin a turn (the conditional update, the message), wait for a confirmation with its card, answer one, finish with the answer and its usage, fail with a reason, and say a turn working for over 20 minutes is stopped (reckoned from its start, or from the handler's answer to a confirmation).
- `backend/copilot_steps.py`: start a step and finish it; trims a result to a readable length.
- `backend/copilot_view.py`: the conversation as the sidebar reads it, and the evaluations' measures without any handler's decision.
- `backend/copilot_service.py`: the one place that asks the Copilot (`start_turn`, `answer_confirmation`, `health`). On the laptop it posts to `UNDERCOVER_COPILOT` with no key; with `UNDERCOVER_COPILOT_RUNTIME` set it invokes that runtime with the conversation's id as the session id and retries Runtime's conflict a few times over a few seconds. A turn the Copilot didn't take is undone, as `starts.py` undoes a run.
- `backend/agent_laptop.py` and `agent_runtime.py`: take the address or the runtime's ARN, the session id and whether to send the key as arguments, so the claim agent's calls are unchanged and the Copilot's use the same plumbing.
- `backend/model_used.py`: `for_copilot()`.
- `backend/customers.py`: customers by name or id with their policies, earlier claims and claims in our queue, and a policy by id.
- `backend/over_limit.py`: the claims in our queue paid over the approval limit, and how many carry a handler's sign-off, in one read.
- `backend/needs_a_handler.py`: the payouts held for sign-off, the claims referred or left for a handler and the sent-back claims the agent hasn't worked (see decision 5).
- `backend/copilot_routes.py` and `backend/lookup_routes.py`: two `APIRouter`s that `main.py` includes, so `main.py` stays thin. The Copilot's own routes: make and list conversations, read one (polled), send a message (202), answer a confirmation, and the Copilot's calls back (start and finish a step, waiting, done, failed). The reads: `customers`, `customers/{id}`, `policies/{id}`, `copilot/evaluations`, `payments/over-limit`, `queue/needs-a-handler`. Every one takes a signed-in handler.
- `backend/auth.py`: the bearer token of a request, for the payload's `sign_in`.
- `docs/SPEC.md`: the three success criteria.

**Success criteria**

- [x] `uv run pytest backend -q` passes, covering through the API with the stand-in Copilot:
  - [x] a message starts a turn: the message is saved, the title is the first question, and the payload has the model from `for_copilot()`, the conversation's id and the sign-in, and no key
  - [x] a second message while a turn works is a 409; after a turn has worked 20 minutes the conversation reads as stopped and a message is accepted; a turn waiting for a confirmation is never stopped and refuses a message
  - [x] a turn the Copilot doesn't take (never connected, an error, a refusal) is undone, with the reason passed on
  - [x] steps arrive as working, then done, refused or failed, in order, and a result is trimmed
  - [x] a waiting confirmation keeps its card until answered, and an answer starts the turn again with the handler's answer
  - [x] a failed turn ends with a short message and the handler can send another
  - [x] another handler is refused a conversation, a message and an answer, with a 403
  - [x] the sign-in is in no table after a turn
  - [x] customers are found by name (partial, any case) and by id; `copilot/evaluations` gives measures and no handler's decision for either set
  - [x] `payments/over-limit` gives 0 and 0 on the seeded queue, and the right counts after a claim over the limit is approved, paid, and signed off (and one without a sign-off, made in the test)
- [x] A test asks every new route with no credentials, with the agent's key alone, and with a handler's, and only the last works. `GET /api/agent/openapi.json` still has exactly the operations it has today.
- [x] `backend/tests/test_connections.py` covers the new flows: no request holds two connections.
- [x] `agent/tests` for `agent_laptop` and `agent_runtime` pass with the claim agent's calls unchanged.
- [x] `uv run pytest -q`, ruff and pyright pass; `docs/SPEC.md` has the three criteria; `docs/STATUS.md` is updated; committed.

## Phase 2: The Copilot's loop, its reads and its actions

The Copilot's graph answers a handler's question with its lookups and its first actions, each step recorded as it happens, and remembers the handler. No pause, no waiting yet.

- `agent/backend_http.py`: `request` (headers given) and `send` (adds the key), as in the design.
- `agent/copilot_api.py`: the Copilot's client to our app: who is signed in, claims, a claim's steps, customers, policies, the latest dispatch, evaluations, settings, needs a handler, starting a dispatch and an evaluation, sending back, and recording steps and turns. Each call carries the sign-in; the only module besides `api.py` and `improver_api.py` that names an `/api/` path.
- `agent/copilot_context.py`: `CopilotContext` (the handler, whether they may sign off, the conversation, the sign-in, the context-only route, the memory) and nothing else.
- `agent/copilot_state.py`: `CopilotState` (the messages, this turn's model calls and cost, and what was remembered).
- `agent/copilot_route.py`: the context-only route, over `GatewayRoute` or `DirectRoute`'s MCP path, refusing the app.
- `agent/copilot_tools.py`: every Copilot tool, at module level. Reads: claims, a claim, a claim's steps, customers, a customer, a policy, the latest dispatch, evaluations, settings, what needs a handler, and the memory search. Actions in this phase: start a dispatch, start an evaluation (the figures in the tool's reply are our app's), and send a decision back. The claim agent's seven context tools are reused from `agent/tools.py`.
- `agent/copilot_recording.py`: wraps each tool call and records its card: the tool's name as the route names it, its main input, the kind, working then done with seconds, or refused or failed with the reason, and a context-layer answer's files with their sources.
- `agent/copilot_nodes.py`: `recall` (the memory lookup at the start of a turn, as a card), `agent` (calls the model; at most 25 calls a turn; adds up calls and cost) and `remember` (saves the handler's message and the answer, nothing else).
- `agent/copilot_memory.py`: the handler's memory over `agent/memory.open_store`, in the actor and session the Memory expects (the handler's id from the sign-in, never from the model or the message).
- `agent/copilot_instructions.py`: the Copilot's goal, who it works for, what it can see and do, the success criteria and how to answer, with no numbered steps.
- `agent/copilot_graph.py`: START to `recall` to `agent`, `agent` to `tools` and back, then `remember` to END.
- `agent/copilot_turns.py`: runs a turn: asks who is signed in (and ends there if refused), builds the context, answers any unfinished tool calls, runs the graph on the conversation's thread, and tells the app the answer, calls and cost, or the failure.
- `agent/harness.py`: a model from a payload's name and effort. `agent/endpoints.py`: `copilot_memory_id()`. `agent/credentials.py`: `fetch` takes the settings to fill, so the Copilot fetches two of the three.
- `agent/tests/test_structure.py`: the Copilot's rules (see design) and `copilot_api.py` joins the HTTP clients.

**Success criteria**

- [x] `uv run pytest agent -q` passes with a stub model, a stand-in memory and the real backend through `TestClient` with a signed-in Dana (the backend tests' signing helper):
  - [x] a turn asks who is signed in before any model call; a refused sign-in ends it with no call to the model
  - [x] a lookup, a customer by name and an action each make a card that goes working, then done with its time, in the app's record; a refused call (the backend's 409 for a second dispatch) is a refused card and the answer passes on the reason
  - [x] every call to the app carries the handler's sign-in and never the agent's key; a context-layer call goes through the context-only route and the app target is refused
  - [x] the sign-in is in no checkpoint (the in-memory saver's storage is searched), no step and no log record
  - [x] a turn stops at 25 model calls with a failed turn and a message; its calls and cost are the turn's totals
  - [x] with memory on, the first card is the lookup with what it found and the turn's end saves the message and the answer and nothing else, as two events, with the handler's id as the actor and the conversation as the session; with it off there is no card and no save; another handler's memory is never searched
  - [x] a turn stopped partway is carried on by a new message, with its unfinished tool calls answered
  - [x] a restart (a freshly built graph on the same saver) carries a conversation on with all its earlier messages
  - [x] the structure tests pass with the new rules
- [x] `uv run pytest -q`, ruff and pyright pass; `docs/STATUS.md` is updated; committed.

## Phase 3: The pause, the wait and the success criteria

The Copilot signs off a held payout only after the handler confirms, waits for the agent's work in code, and answers whether we're meeting the criteria from our records.

- `agent/copilot_confirm.py`: the `confirm` node. It checks in code that the handler may sign off that claim (and that the claim is waiting for one), declines in the model's own terms if not, and otherwise reads the claim, customer, payout and the agent's reason from our records and pauses with them. A confirmed answer leaves the sign-off to `tools`; Cancel answers the call itself and the model asks what else. A second sign-off in the same reply is answered "one at a time".
- `agent/copilot_tools.py`: `sign_off_claim` (the app's sign-off, which pays), `start_dispatch` and `start_evaluation` with `wait`, and `check_success_criteria`.
- `agent/copilot_waiting.py`: polls a run every few seconds through `GET /api/runs/{id}` and stops after 15 minutes, saying the work is still going and where to follow it.
- `agent/copilot_criteria.py`: the three criteria in `Decimal`: the held-out evaluation's `straight_through` against 70%, its `accuracy` against `objective_accuracy`, and the count of claims paid over the limit with their sign-offs (met, and say why, when none is paid over it yet).
- `agent/copilot_graph.py`: `after_agent` sends a reply with a sign-off to `confirm`, other tool calls to `tools` and a plain reply to `remember`.
- `agent/copilot_turns.py`: when the graph returns an interrupt, tells the app the turn is waiting, with the card; `answer_confirmation` resumes the same thread with `Command(resume=...)`.

**Success criteria**

- [ ] `uv run pytest agent -q` passes, adding:
  - [ ] a sign-off call pauses with a card whose claim, customer, amount and reason are our records', not the model's arguments; nothing is paid and no write is made before the answer
  - [ ] a handler who can't sign off over the limit (Marcus) is declined in code with the reason, with no card and no pause; a claim that isn't waiting is declined the same way
  - [ ] a freshly built Copilot on the same saver, given the answer, signs off once (the backend's claim is decided, paid and names the handler), and nothing done before the pause is done again (counted on the stand-in app)
  - [ ] Cancel pays nothing and the Copilot says so and asks what they'd like
  - [ ] the answer arrives after a reload, a restart and with another session (a second graph object): the same result
  - [ ] a wait ends when the run does, with its summary; at 15 minutes (a fake clock) it says it is still going; a dispatch the app refuses (one is running) passes on the reason; and the wait never calls the model
  - [ ] the criteria come out right for: all three met; each one failing in turn; no claim paid over the limit; one paid over without a sign-off (made in the test); and an evaluation that failed or stopped (no figures for the first two, the third still reported); and the figures in the answer are the tool's
  - [ ] a mixed reply (a sign-off with another lookup) runs the lookup and pauses once
- [ ] `uv run pytest -q`, ruff and pyright pass; `docs/STATUS.md` is updated; committed.

## Phase 4: The Copilot as an AgentCore app, and its deployment files

The Copilot answers its health check through the file Runtime starts, takes a turn and answers at once, and the deployment project holds it as a second runtime. Nothing is deployed.

- `agent/copilot_operations.py`: the payload's operations (`start_turn`, `answer_confirmation`, `health`), each with its own inputs and a 400 that says what is wrong; the answer `{"accepted": true}`, `{"refused": ...}` or `{"healthy": true}`.
- `agent/copilot_readiness.py`: gets ready on the first request, once: fetches `OPENROUTER_API_KEY` and `DATABASE_URL` from Identity on Runtime and opens the checkpoint pool. It never asks for the agent's key, and nothing happens at import.
- `agent/copilot_entrypoint.py`: the Copilot's `BedrockAgentCoreApp`, one entrypoint, each turn registered as an async task through `agent/background_work.py` as the claim agent's are, so the session lasts as long as the turn. On the laptop it asks for no key.
- `runtime/copilot.py`: the file Runtime starts; it imports the app and runs it.
- `runtime/copilot_policy.json`: the Gateway and the Copilot's Memory (`undercover_copilot_memory-*`) for its role.
- `agentcore/agentcore.json`: the `copilot` runtime beside `agent`, with the same credentials and its own policy; `agentcore/cdk/lib/cdk-stack.ts`: `UNDERCOVER_COPILOT_MEMORY_ID` goes to the Copilot's runtime only. The platform team's files change only where this needs it.
- `package.json`: `dev:copilot` serves the app on 127.0.0.1:8081 with reload, `dev` starts it, and `check:runtime` also imports `runtime.copilot`.
- `docs/TECH_STACK.md` (the Copilot's part and its Deployment lines), `docs/CODE_STANDARDS.md` (the Copilot as a part of its own, with the same rules, and `copilot_tools.py` as the improver's tools are) and `docs/PROCESS.md` (`npm run dev` starts it).

**Success criteria**

- [ ] `uv run pytest agent -q` passes: a payload with a missing or wrong input, or an unknown operation, is a 400 that says what; `health` answers without a key; `start_turn` answers `accepted` at once and the turn goes on as a registered task (the ping says `HealthyBusy`); getting ready fails once and works on the next request; nothing is fetched or opened at import.
- [ ] `npm run check:runtime` passes, and `uv run --env-file .env --isolated --only-group runtime python -m runtime.copilot`'s app answers `{"operation": "health"}` with `{"healthy": true}` on 8081, with only the `runtime` dependency group.
- [ ] `agentcore/agentcore.json` has two runtimes, both on V2 through the stack's override; `npx cdk synth` through `agentcore/cdk` (or the CLI's own dry run, if it has one) shows both runtimes and the Copilot's role with its policy, without deploying; the claim agent's runtime is unchanged.
- [ ] `npm run dev` starts the Copilot beside the rest on 8081. A test serves the Copilot's app on a local port with a stub model, as the claim agent's tests serve theirs, and the app reaches it: a message to `POST /api/copilot/conversations/{id}/messages` starts a turn there and the turn's steps and answer come back through the app. No test calls a real model.
- [ ] `npm run check:python`, `check:server`, `check:context` and `check:runtime` pass; the docs are updated; committed.

## Phase 5: The sidebar

A handler sees and uses the Copilot on every page: a conversation with each step as a card, a confirmation card, and the earlier conversations.

- `dashboard/src/api.ts`, `types.ts`: the conversations, a conversation as polled, sending a message, answering a confirmation, and each step's kind and state, checked on arrival like everything else. A step of a kind it doesn't know is refused, as the claim page's are.
- `dashboard/src/auth.ts`: renews the sign-in when it has under 20 minutes left; `api.ts` does that before a message or an answer is sent.
- `dashboard/src/usePolling.ts`: the interval becomes an argument (two seconds by default), so the sidebar asks about once a second while a turn works and not while idle.
- `dashboard/src/useCopilot.ts`: one conversation's state, polling and sending; `dashboard/src/sidebarPreference.ts`: whether the sidebar is open, kept in the browser, open the first time.
- Components: `CopilotSidebar.tsx` (the shell: right of the page, a slim tab with an icon of its own when collapsed, over the page on a narrow window), `Conversation.tsx` (the messages and cards), `StepCard.tsx` (icon by kind, name, main input, state with spinner and seconds, opens to what was asked and what came back, with files and owners; an action stands out), `ConfirmationCard.tsx`, `AnswerText.tsx` (markdown, with claim ids linked to their pages), `Composer.tsx` ("Ask the Copilot", Enter sends, Shift+Enter starts a line, disabled while a turn works and asks for the confirmation first), `ConversationList.tsx` (New conversation, and the earlier ones, newest first) and `CopilotIcons.tsx`.
- `dashboard/src/App.tsx`: the shell mounts the sidebar beside the routes; `theme.css`: the sidebar in the brand's fonts and colors in light and dark.
- `e2e/copilotStandIn.mjs` (port 8007) plays a scripted turn through our app with the handler's sign-in: a lookup, an action, a refusal, a confirmation and a formatted answer; `e2e/copilot.spec.ts` drives it; `playwright.config.ts` points the app at it.
- `docs/TECH_STACK.md`: the dashboard line.

**Success criteria**

- [ ] `npm run check:ts` passes with 80% coverage: component tests for a card in each state and kind, the confirmation card's two buttons, answer text (a table, a list, a claim id link, raw HTML shown as text), the composer's keys and its disabled states, the list, the collapse and its memory, the narrow window's overlay, and the renewal of a sign-in under 20 minutes.
- [ ] `npm run e2e` passes, adding the Copilot's spec (the scripted turn's cards arrive one by one; the action's card stands out; a refusal shows its reason; Cancel and Sign off and pay each work; a reload keeps the waiting card; a second handler doesn't see the first's conversation), and every existing spec passes with the sidebar open.
- [ ] Checked in the browser (Playwright MCP) against the stand-in, in light and dark mode: the greeting and suggested questions, the cards' animation, the markdown, the collapsed tab, and a narrow window; the fonts and colors match `docs/BRAND.md`, with no one-edge borders or gradients.
- [ ] `npm run check` is green with `.env` moved out of the way; `docs/STATUS.md` is updated; committed.

## Phase 6: The live checks and the last of the documents

After one reseed, with `npm run dev` running on the default model, the direct route and memory off. Nothing here deploys anything.

- Ask you to run `npm run seed` with `npm run dev` stopped, then start `npm run dev`.
- As Dana Whitfield (Playwright MCP, with `HANDLER_PASSWORD` from `.env` and the password kept out of the transcript), in one conversation, the five questions of the handover.
- `docs/SPEC.md`, `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/STATUS.md` describe the product as it now is, and the whole change is reviewed once more against the checklist in `docs/CODE_STANDARDS.md`, including the code it touched outside its own area.

**Success criteria**

- [ ] 1: "Work the queue with 10 agents and tell me what needs me." The dispatch starts as Dana, the claims move behind the sidebar, the Copilot waits without model calls, and its answer's groups match the queue and the dispatch's summary.
- [ ] 2: "Why does CLM-... need me?" about a held payout: cards for the claim, the agent's steps and context-layer lookups, and an answer that agrees with the claim's page.
- [ ] 3: "Send it back with a note": the claim is sent back as Dana, with her note, on its page.
- [ ] 4: "Sign off on another one": a confirmation card with the claim, customer, amount and the agent's reason; nothing paid until Sign off and pay; then the claim is paid once with Dana's name and the time on its page. A reload before answering keeps the card.
- [ ] 5: "Are we meeting the success criteria we agreed?": a whole held-out evaluation runs, the Copilot waits, and the table's figures match the Scoreboard and the claims' pages (checked by eye against both), with one line on whether all three are met.
- [ ] After `npm run dev` is restarted, the same conversation is picked up with its history and the Copilot continues it.
- [ ] Signed in as Marcus Oyelaran, "sign off on CLM-..." is declined with the reason, with no card.
- [ ] No response, log, step or table holds a sign-in token (checked by searching the database and the dev logs for the token's first characters).
- [ ] The sidebar in light and dark mode, checked on the queue page and a claim page.
- [ ] I report what the runs spent. By our earlier runs, a dispatch of the whole queue was about $0.044 and a held-out evaluation about $0.05; the Copilot's own turns should add a few cents. The Memory is checked on the deployed product by your notebook, not here.
- [ ] `npm run check` is green with `.env` moved out of the way; the documents describe the product as it is.

## Not for now

As the brief says: streaming word by word, stopping a turn partway, reading the claim agent's memory of customers, sharing, renaming or deleting conversations, changing settings, the configuration or rounds through the Copilot, and Langfuse for the Copilot.

I stop here, with no code written, until you ask me to implement the plan.
