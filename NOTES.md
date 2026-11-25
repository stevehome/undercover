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

## Week 3 Day 4 lab 2 challenge: the held-out evaluation on Runtime and on the laptop

The challenge asks to run the held-out evaluation with the agent on Runtime, run it again on the laptop, and compare time per claim and cost. `scripts/compare_runs.py` prints the comparison from the database (`uv run --env-file .env python scripts/compare_runs.py runtime=16,17 laptop=21,22`); it only reads.

All runs are the held-out set, 25 claims, 25 agents at once, `openai/gpt-6-luna` at medium effort, configuration version 2.

| | Runtime, Lambda limit 10 (runs 16, 17) | Runtime, limit 1000 (runs 24, 25) | Laptop (runs 21, 22) |
|---|---|---|---|
| Refusals by the context layer | 158 and 203 | 0 and 0 | 0 |
| Model calls | 303 and 299 | 216 and 210 | 214 and 214 |
| Wall time per claim | 8.5 to 9.1 s | 5.4 and 5.9 s | 6.7 to 6.9 s |
| Working time per claim | 136 to 141 s | 64 and 62 s | 117 to 122 s |
| Cost per claim | $0.0018 to $0.0020 | $0.00195 and $0.00203 | $0.0019 |

1. **Cost is the same on both routes**, about $0.0019 to $0.0020 a claim ($0.048 to $0.051 for the run). That is the model's cost as the app records it; the AWS bill for Runtime and Lambda is not in it.
2. **The first Runtime runs were slower than the laptop and made about 40% more model calls, because Lambda throttled them.** The Gateway's calls to the context layer's Lambda, and the Gateway's calls to the app, answered 429 (`ConcurrentInvocationLimitExceeded`, or "returned HTTP 429 to the initialize handshake"). The agent passes that on as "Refused by the context layer: ...", and the model asks again, often with a different query. Found by comparing `claim_steps` for CLM-1111: run 16 had 11 refusals and 22 model calls over 205 s; run 21 (laptop) had none and 9 calls over 120 s. Nothing else differed: the agent code is the same package on both routes, the configuration version is the same, and memory is off for evaluation claims (`agent/memory.py` `open_for`). The laptop calls the app and the context layer directly, so it never goes through the Gateway or the limit.
3. **Raising the Lambda "Concurrent executions" quota from 10 to 1000 (Service Quotas, `us-east-1`) removed it.** Runs 24 and 25 had no refusals and 216 and 210 calls, and were about 20% and 11% faster than the laptop by wall clock (134 s and 149 s against about 170 s for the run). It is two Runtime runs and two laptop runs, and the laptop reaches the database in `eu-west-1` over home internet, so treat the gap as indicative.
4. **The agent now tries a Gateway call again after a 429** (`agent/gateway.py`, commit `e399307`, up to 6 tries with a growing wait). It matches only the three message forms above, so a refusal that merely contains "429" is left to the model. Run 24 was made without it. It was deployed as runtime version 5 (19:05 UTC), and run 25 ran on it with the same results as run 24, but with the quota at 1000 nothing was throttled, so the retry was not used; it is covered by tests only.
5. **The runtime's logs do not show a claim.** The log group `/aws/bedrock-agentcore/runtimes/undercover_default_agent-mhoaRxCQpr-DEFAULT` has one stream per session, and an evaluation is one session: "Async task started: run" and "Async task completed: run" around the whole 25 claims (18:14:51 to 18:16:54 for run 24), with the startup lines (`Created a workload identity`) and nothing per claim. A claim's steps, with timing, are in `claim_steps` and its calls in `model_calls`. Per-claim lines in the logs would need the agent to log each tool call, and a redeploy.
6. **The IAM user cannot list quota requests** (`servicequotas:ListRequestedServiceQuotaChangeHistoryByQuota` is denied), so the request was made in the console. It could read the value (`aws service-quotas get-service-quota --service-code lambda --quota-code L-B99A9384 --region us-east-1`).
