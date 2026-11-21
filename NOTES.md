# Notes

## Week 1 Day 4 lab: flaky OpenRouter provider for DeepSeek V4.1 Flash

Running `deepseek = run("deepseek/deepseek-v4.1-flash", "low", claims, labels)` in `labs/week1day4.ipynb` raised a pydantic `ValidationError` — `EOF while parsing a string` — because one of OpenRouter's providers for that model returned truncated JSON while still reporting `finish_reason: "stop"`.

Checked by reproducing the single-claim call directly (bypassing `.parse()` so the raw response could be inspected): across all 20 claims and several different providers (Together, InferenceNet, Morph, Wafer, CoreWeave, Relace, ModelRun, Cohere, Fireworks), every call came back with valid, complete JSON and `finish_reason: "stop"`. So it's not a systematic problem with the prompt, the schema, or a token limit — it's the same class of issue the lab already documents for GLM 5.3 Flash's `wafer` provider (cell 33), just intermittent and on a different provider this time.

Fix: gave `decide()` (cell `c60b9b2c`) a small retry — up to 2 attempts, retrying on `ValidationError` — since OpenRouter's routing is non-deterministic per call, so a retry likely lands on a working provider. Added `ValidationError` to the pydantic import in cell `bac9c230`.

## Week 3 Day 2 lab 2: `KeyError: 'undercover-app___search_documents'`

`await call_tool("search_documents", query="unattended")` in `labs/week3day2_lab2.ipynb` (cell 52) raised `KeyError: 'undercover-app___search_documents'`. The `KeyError` is not an `McpError`, so `call_tool`'s `except` did not catch it.

Cause: the lab and the brief (`docs/SECURE.md`) assume the agent's API has eight operations, including `search_documents`. Our build's `GET /api/agent/openapi.json` has six (`get_claim`, `list_sections`, `get_section`, `calculate_payout`, `decide_claim`, `pay_claim`), which we kept from Phase 3 of `docs/PLAN_SECURE.md`. The Gateway makes a tool of each operation in the document it is given, so `tools` has no `search_documents` key. The brief's `get_policy` and `get_claim_history` are in our `get_claim`, `read_section` is our `get_section`, and `record_decision` is our `decide_claim`.

Fix: in cell 52 call one of ours, such as `await call_tool("list_sections", document="policy_wording")`. `document` is `policy_wording` or `claims_manual`; `get_section` also takes the `heading`. `get_claim` and `pay_claim` (with `amount`, which the Gateway's Policy reads) work as the lab has them. If a later lab names `search_documents` or `record_decision`, it needs the same change.
