# Role play: the forward deployed engineer answers the business's questions

Four questions from UnderCover's side about the platform as it stands at the end of the Week 2 Day 5 build. The answers are my opinions as the coding agent, grounded in the code and docs. They are not legal advice. Where I haven't verified something, I say so.

Evidence: `agent/harness.py`, `agent/tracing.py`, `backend/judge.py`, `backend/auth.py`, `backend/tables.py`, `data/customers.json`, `data/handlers.json`, `docs/SPEC.md`, `docs/TECH_STACK.md`.

## 1. Does the app respect data privacy and typical data protection law (GDPR, UK GDPR, CCPA)?

**Short answer: not yet. It is built sensibly, but it has no privacy design, and that matters before real customers.**

What is in the product's favour:

- Handlers sign in through Supabase Auth with sign-ups off, and the backend checks the handler on every action a handler takes.
- The claim agent reaches data only through the backend's API, never the database directly. That gives us one place to apply controls.
- The held-out answer key is walled off from the claim agent. That is an integrity control, not a privacy one, but it shows the pattern works.
- Every sign-off, setting change and proposal approval records who and when, which is a good audit trail.

What is missing, in order of concern:

1. **Personal data goes to the model.** A claim carries the customer's story and documents. A customer record holds name, email, phone, date of birth, address and claim history. The agent reads these through its tools, so they reach OpenRouter and the model provider. Under GDPR that is a transfer to processors, and the customers' personal data includes health information in medical claims (special category data, Art. 9). We need a lawful basis, a data processing agreement with each processor, and a transfer mechanism if data leaves the EU or UK. None of that exists in the repo.
2. **Minimisation.** The agent gets whatever the tools return. No field is redacted or pseudonymised first. Date of birth and street address are probably not needed to decide a trip delay. I'd cut the tool output to the fields the decision needs.
3. **Langfuse holds full prompts and replies.** `agent/tracing.py` traces every claim, so claim content and customer details are copied into a second third-party system. I haven't checked which Langfuse region or plan is configured. That is a second processor and a second retention question.
4. **No retention or deletion.** Nothing deletes a customer's data, the agent's saved progress (the LangGraph checkpoints in Postgres) or the traces. Erasure and access requests (Art. 15 and 17) would be manual work across Supabase, checkpoints and Langfuse.
5. **Reads are open.** `docs/TECH_STACK.md` says the agent's own routes and the reads under `/api/runs` stay open until Week 3's API key. Anyone who can reach the backend can read claims. That is acceptable on localhost and unacceptable on the internet. Week 3 Day 2 is where this closes.
6. **Automated decisions.** GDPR Art. 22 gives people rights around decisions made solely by automated means with significant effects. Today a payout over $1,000 waits for a handler, but declines, refers and payouts under the limit are final without a human. A decline is the one that most needs a human route: the customer should be able to ask for a person to review it. I'd also record the agent's reasons in a form we can give the customer.
7. **Data subjects and records.** We need a record of processing, a privacy notice that mentions AI-assisted decisions, and probably a data protection impact assessment, because this is automated decision-making on health-related data.

My recommendation: before any real claim goes through, do a DPIA, sign DPAs with OpenRouter, the model providers, Supabase and Langfuse, minimise what the tools return, and set a retention period with a deletion job. The data in `data/` is synthetic (`example.com` addresses), so nothing is breached today.

## 2. Is encryption used in calls to OpenRouter and the models behind it?

**In transit: yes, to OpenRouter. After that I can't vouch for it.**

- `agent/harness.py` sets `OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"` and `backend/judge.py` defaults to `https://openrouter.ai`, so both calls use TLS.
- OpenRouter is a router: it forwards each request to a provider (OpenAI, Anthropic, Google, a hosting company and so on). OpenRouter's side is its own contract with those providers. I believe they use HTTPS, but we don't control or see it, so treat it as an assumption to confirm in OpenRouter's documentation and security statement.
- The Supabase connection (`DATABASE_URL`, the session pooler) is Postgres over the network. Whether TLS is required depends on the connection string's `sslmode`. I haven't checked that, and I'd set `sslmode=require` or stronger.
- Langfuse calls go to its host over HTTPS by default, but I haven't checked the configured host.
- **Inside our own system the calls are plain HTTP on localhost**: the dashboard, backend (:8000) and agent service (:8002). That is fine on one machine. On AWS in Week 3 the traffic between services must be inside a private network or on TLS.
- **At rest**: Supabase encrypts its disks. The local SQLite file `backend/undercover.db` is unencrypted, which is fine for synthetic data only.
- The API key is held as a `SecretStr` and read from `.env`, which is not in git. It is not yet in a secrets manager, and Week 3 moves it.

## 3. Can any of the models "call home" or train on our data?

**The models themselves can't call home. Their operators can keep and use what we send, and we haven't told OpenRouter to prevent that.**

- A model reached through an API has no network access of its own. It only sees what we send and returns text. The one way a model could reach out is through tools, and ours are only the backend operations we wrote in `agent/tools.py`. A prompt injection hidden in a claim could try to misuse them, which is why Week 3 Day 2 adds a check for hidden instructions.
- The real exposure is the provider. Every prompt goes to OpenRouter and then to a provider that may log it, retain it, or in some cases train on it, depending on that provider's terms and our OpenRouter settings. OpenRouter lets an account and each request restrict routing to providers that don't train on or retain prompts (a data-collection setting and a zero-data-retention option). I searched `agent/` and `backend/` and found that **neither is set in the code**. The account settings are covered below. The field names are from OpenRouter's [provider routing documentation](https://openrouter.ai/docs/guides/routing/provider-selection).
- The `openrouter/free` route that the course offers is the worst case. Free models commonly train on prompts, so it must never see real customer data.
- Model choice is a data decision as well as a cost one. The `models` table lists the models allowed. I'd add a field to it for the provider's data terms and only allow models whose terms we've approved.
- The judge (`jev`) and Langfuse are two more places that see claim content. Each needs the same answer.

### Checked on 2026-11-16: OpenRouter's account privacy settings

I read the Personal account's privacy page (`/settings/privacy`) and changed nothing. OpenRouter's documentation says no-training (`data_collection: "deny"`) and zero retention (`zdr: true`) are separate controls, and that a request can add a restriction to the account's settings but can't remove one.

| Setting | State |
|---|---|
| Allow paid endpoints that train on request data | Off (good) |
| Allow free endpoints that train on request data | **On** |
| Allow free endpoints that publish prompts to public datasets | **On** |
| 1% data discount in workspaces | Off (good) |
| Zero Data Retention (all models, and Anthropic, OpenAI, Google, SpaceXAI) | **All off** |
| Allowed or ignored providers | Empty, so all are allowed |
| Regional routing (EU or US) | Business plan only, not on |

What that means:

- **Paid models** can't train on our prompts, because the account blocks it, even though the code doesn't ask.
- **Free models** may retain, train on and publish prompts. They must never see real customer data.
- **Retention** isn't restricted anywhere, so paid providers may keep prompts for a time without training on them.
- **EU or US residency** needs the Business plan. If UnderCover must keep data in the EU, that is a plan decision.
- I did not open the workspace guardrails, which can restrict keys further.

**Update, same day:** the account owner turned off both free-endpoint switches and turned on Zero Data Retention for all other models, set to "Allow Safety Retention" (not "ZDR only"). `agent/harness.py` and `backend/judge.py` now send `provider: {data_collection: "deny", zdr: true}` on every call. After both changes, a live call for the claim agent's model, one for the improver's model (`openai/gpt-6-luna`) and one to the judge (Jev) all succeeded. What remains open:

- "Allow Safety Retention" lets some endpoints, such as open-weight models on Vertex, keep prompts briefly to prevent abuse, without training on them. "ZDR only" would remove that. I'd choose it once the models in use are checked against it.
- The Anthropic, OpenAI, Google and SpaceXAI switches are off. Turning them on would block those providers' own first-party endpoints and leave only their cloud partners. I'd leave them off unless the contract needs it.
- Workspace guardrails and the regional routing (Business plan) are unchanged.

The original next steps, now done except the "ZDR only" choice:

1. Turn off the two free-endpoint switches.
2. Turn on zero retention for all other models, then run one claim to confirm the default model still works, because zero retention narrows the providers a model can use.
3. Add `provider: {data_collection: "deny", zdr: true}` to the model calls in `agent/harness.py` and `backend/judge.py`, so the rule travels with the app and doesn't depend on one account.

My recommendation: do all three, make the rule a platform setting a handler can see, keep a list of approved providers with their terms, and use no free models with real data.

## 4. Is a named individual responsible for all of the agents?

**No. People are named for actions, but nobody is named for the agents.**

What exists:

- Handlers are named people (`data/handlers.json`), and each human action records who and when: sign-offs, setting changes, proposals approved (`approved_by`), rounds.
- Dana Whitfield is the senior handler, and she is the only one who can change settings, approve the improver's proposals, or sign off over the limit.
- Every run records its configuration version, so we can tell which instructions and model made a decision.

What doesn't:

- There are three kinds of agent: the claim agents (up to 25 at once), the dispatcher (no model) and the improver. None has an owner in the data or the docs. Dana is the de facto approver of changes, but nothing says she answers for what a claim agent decides, for what the improver learns or for a privacy incident.
- Agents run under one shared service identity (the `OPENROUTER_API_KEY` and a shared database login). If a claim is wrongly paid, the record shows the agent version but not which human is accountable.
- The improver changes the claim agent's instructions through proposals a human approves. That is good, but the approver has a small senior pool and no deputy.

My recommendation, in order:

1. Name an **accountable executive** for the whole AI claims capability. The natural choice is the head of claims operations, who wrote the spec.
2. Name a **responsible owner** for each of the three agents, and a deputy. Dana could own the claim agents, and someone else could own the improver, so the same person doesn't both build and approve its changes.
3. Add an **agent register**: name, purpose, owner, deputy, model and provider, data it can see, tools it can use, approval limit and review date. It can be a table in the database and a page in the dashboard, so the roster is as visible as the handlers.
4. Add a **data protection officer** or a named privacy lead for questions 1 to 3.
5. Write an **incident route**: who is called when an agent pays wrongly, leaks data or is injected, and who can stop all runs. The stop control exists in the dashboard. The rule about who may press it doesn't.

## Priorities

| # | Action | Why first |
|---|---|---|
| 1 | Turn off the free-endpoint switches, turn on zero retention, and set both in the code | Checked 2026-11-16: free models may train on and publish prompts, and retention is unrestricted |
| 2 | Name the accountable executive and an owner for each agent | Costs nothing and decides who does the rest |
| 3 | Close the open routes with the Week 3 API key, and require TLS on the database | Already planned for Week 3 |
| 4 | Minimise the tool output and the traced content | Reduces every other risk |
| 5 | DPIA, DPAs, retention and deletion, a human review route for declines | Needed before real customers |
