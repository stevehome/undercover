# Notes

## Week 1 Day 4 lab: flaky OpenRouter provider for DeepSeek V4.1 Flash

Running `deepseek = run("deepseek/deepseek-v4.1-flash", "low", claims, labels)` in `labs/week1day4.ipynb` raised a pydantic `ValidationError` — `EOF while parsing a string` — because one of OpenRouter's providers for that model returned truncated JSON while still reporting `finish_reason: "stop"`.

Checked by reproducing the single-claim call directly (bypassing `.parse()` so the raw response could be inspected): across all 20 claims and several different providers (Together, InferenceNet, Morph, Wafer, CoreWeave, Relace, ModelRun, Cohere, Fireworks), every call came back with valid, complete JSON and `finish_reason: "stop"`. So it's not a systematic problem with the prompt, the schema, or a token limit — it's the same class of issue the lab already documents for GLM 5.3 Flash's `wafer` provider (cell 33), just intermittent and on a different provider this time.

Fix: gave `decide()` (cell `c60b9b2c`) a small retry — up to 2 attempts, retrying on `ValidationError` — since OpenRouter's routing is non-deterministic per call, so a retry likely lands on a working provider. Added `ValidationError` to the pydantic import in cell `bac9c230`.

## Week 3 Day 2 lab 2: `KeyError: 'undercover-app___search_documents'`

`await call_tool("search_documents", query="unattended")` in `labs/week3day2_lab2.ipynb` (cell 52) raised `KeyError: 'undercover-app___search_documents'`. The `KeyError` is not an `McpError`, so `call_tool`'s `except` did not catch it.

Cause: the lab and the brief (`docs/SECURE.md`) assume the agent's API has eight operations, including `search_documents`. Our build's `GET /api/agent/openapi.json` has six (`get_claim`, `list_sections`, `get_section`, `calculate_payout`, `decide_claim`, `pay_claim`), which we kept from Phase 3 of `docs/PLAN_SECURE.md`. The Gateway makes a tool of each operation in the document it is given, so `tools` has no `search_documents` key. The brief's `get_policy` and `get_claim_history` are in our `get_claim`, `read_section` is our `get_section`, and `record_decision` is our `decide_claim`.

Fix: in cell 52 call one of ours, such as `await call_tool("list_sections", document="policy_wording")`. `document` is `policy_wording` or `claims_manual`; `get_section` also takes the `heading`. `get_claim` and `pay_claim` (with `amount`, which the Gateway's Policy reads) work as the lab has them. If a later lab names `search_documents` or `record_decision`, it needs the same change.

## Week 3 Day 4 lab 2: running the deployed app and agent

Eight problems turned up when a swarm, and then an improvement round, ran on the deployed app (Lambda) with the agent on Runtime. Each cause was checked in the logs, the database or AWS before the fix.

1. **A swarm of 25 stopped after 3 claims.** The account's Lambda concurrency limit is 10, and 25 agents call the app at once, so Lambda answered 429 `ConcurrentInvocationLimitExceeded`. The agent took the 429 as a refusal and stopped the dispatch ("The agent's work failed: ApiRefusal"), leaving 3 claims "in progress" with expired leases. Fix: `agent/backend_http.py` sends a request again after a 429 (up to 8 tries, waiting longer each time, with jitter), since a throttled request was never run. The stuck claims were reset to `waiting` by hand. The real fix is a higher quota (Service Quotas, "Concurrent executions"), which costs nothing; Lambda charges for requests and duration, not for the limit.

2. **The app was slow, a median of 1.3 s a request.** The Supabase pooler is in `eu-west-1` and the Lambda in `us-east-1`, and the app opened a new database connection for every request. Fix in `backend/db.py`: on Lambda the engine keeps one connection per instance (`pool_size=1`, `pool_pre_ping`), and every Postgres statement names its schema (`schema_translate_map`), since the pooler sometimes dropped the `search_path` option and a request failed with `relation "handlers" does not exist`. Result on the same 26 claims with 3 agents: median 1.3 s to 0.62 s, p95 3.3 s to 1.55 s, and the run took 8 min 39 s. The queue page's "21 min working time" adds up the time of all three agents, so it isn't the time on the clock. Moving the Supabase project to `us-east-1` would cut the rest, but it was not done.

3. **Starting a round, or opening the Improvement page, hung and failed (a 502 after 30 s, "Could not load the latest").** The fix in 2 caused it: with a pool of one, code that opens a second connection inside the first waits for the pool's timeout. `list_rounds`, `create_round` and the proposal decision did. They now read what they need before the connection opens, and `backend/tests/conftest.py` has a fixture that fails any test where a connection opens inside another, so the project's "one connection at a time" rule is enforced. The laptop's pool of four had hidden it.

4. **The judge could not grade on Lambda (`KeyError: 'OPENROUTER_API_KEY'`).** The app's environment had three variables and the judge in `backend/judge.py` needs the key. Added `OPENROUTER_API_KEY` to the `environment` dictionary in cell 21 of `labs/week3day2_lab2.ipynb` and to `app_environment` in cell 10 of `labs/week3day4_lab2.ipynb`.

5. **Every round and dispatch stopped with "The agent did not take the work".** The Lambda was missing `UNDERCOVER_AGENT_RUNTIME`, so the app tried the laptop agent at `127.0.0.1:8080`. Redeploying the app with the Day 2 cell 23 (or Day 4 cell 10) replaces the whole environment, and cell 27 of this lab is what sets the variable. Run cell 27 after every redeploy of the app. Cell 27 also sets the whole environment from `app_environment`, so cell 10's dictionary must have all the variables, which is why the key in 4 went there too.

6. **`agentcore deploy` finished with a warning and changed nothing.** The project pinned `@aws/agentcore-cdk` at `1.0.0-rc.3` and the CLI (`1.0.0-rc.7`) wants `rc.4` or newer. The runtime stayed on version 2 and the CloudFormation stack was not updated. The CDK package has its own version numbers: there is no `rc.7` of it, so pin `1.0.0-rc.4` in `agentcore/cdk/package.json`.

7. **After the new CDK, the agent answered `UNDERCOVER_API_KEY is missing: set it in .env`.** `rc.4` names the runtime's credential settings `CREDENTIAL_<NAME>_NAME`, where `rc.3` named them `AGENTCORE_CREDENTIAL_<NAME>_NAME` (checked by reading the environment of runtime versions 2 and 3). The agent found none, decided it was on a laptop and asked for `.env`. `agent/credentials.py` now reads both names. `docs/RUNTIME.md` still shows the old one.

8. **"Could not load the latest" while a round's evaluations run.** The setting `improver_agents_at_once` is 25, against a limit of 10 concurrent Lambdas, so Lambda throttled 177 requests in 5 minutes. The agents retry (see 1) and the round carries on, but the dashboard does not retry a failed poll. Lower the setting to about 8 on the Settings page, or raise the quota. The dashboard still shows the message when a poll is throttled.
