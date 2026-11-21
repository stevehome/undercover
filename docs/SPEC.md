# The claims pilot

From the head of claims operations at UnderCover Travel Insurance.

## How claims work today

UnderCover sells travel insurance on three plans: Economy, Premium and First. Our three claims handlers work through a queue of claims by hand. For each claim, a handler reads the customer's story and documents and checks them against the policy and our policy wording. Then they approve the claim with a payout, decline it or refer it. A claim is referred when it needs someone's judgment or more information, as the claims manual explains.

## The pilot

We want an AI agent, the UnderCover Agent, to work the queue the way a handler does. For each claim it should:

- read the claim, the customer's policy and claim history, the policy wording and the claims manual
- approve, decline or refer the claim
- work out the payout when it approves
- explain the decision in two or three sentences, along with the relevant section of the policy

Our goal is to handle claims straight through, as accurately as our handlers do.

A handler starts a dispatch on the queue page, choosing how many claim agents work at once, from 1 to 25. A dispatch works every claim left in progress and every waiting claim, oldest submitted first, with no model choosing the order. Only one dispatch or evaluation runs at a time. The page shows each claim of the dispatch and where it stands, the model cost and the time, and when the dispatch ends a summary built from our records: how many claims were approved, declined and referred, each payout waiting for a sign-off, and each claim left for a handler or still in progress. A claim shows as in progress while the agent works on it. Someone can also start the agent on one named claim from the command line.

When the agent approves a payout over $1,000, it stops and waits for a handler, keeping everything it has worked out. When a handler signs off on the dashboard, the sign-off pays the claim in the same step, and the payment records who signed off and when. The agent doesn't need to be running. The agent itself never pays more than $1,000: the backend refuses any payment over the limit, so only a sign-off pays more. A handler can only sign off for now; rejecting a held payout comes later.

If the agent is stopped partway through a claim, by a crash, a restart or Ctrl-C, it carries on with that claim from where it got to the next time it runs, and that doesn't count as a new attempt. A claim that hits a rate limit or a timeout waits and carries on from where it got to, and if it is still hitting them it stays in progress for the next dispatch. A claim that fails with any other error goes back in the queue and the same dispatch tries it once more, and a claim that fails twice is left for a handler. One bad claim never stops a dispatch. A dispatch that was stopped is finished by the next one. No claim is ever decided or paid twice.

## Signing in

Handlers sign in to the dashboard with their email address and password, through Supabase Auth. There is no sign-up. Every page needs a signed-in handler, and the header shows who is signed in, with a way to sign out. The backend checks the handler on every action a handler takes: signing off a payout, starting a dispatch, an evaluation or a round, stopping a round, approving or rejecting a proposal and changing a setting. A sign-off records the signed-in handler. Dana Whitfield is the senior handler. Only a handler who can sign off payouts over the limit may start or stop a round, approve or reject the improver's proposals or change a setting. When anyone else looks at a held payout, a round or the settings, the page says what they can't do and why, and the backend refuses it as well.

The agent has its own way in: an API key, which the backend checks on every route the agent uses. The agent's routes accept only the key, and what both the agent and the dashboard read accepts the key or a signed-in handler. Everything else the dashboard shows needs a signed-in handler, and a handler's sign-in never works on the agent's routes. Only the health check is open. The agent's service won't start without the key.

## Hidden instructions

Everything in a claim comes from the customer, so some claims will carry text written for the AI: an instruction to approve in full, or a claim that someone at UnderCover has already approved it. Every claim is checked for this before the claim agent sees it. A second model reads the claim, and a claim with an instruction in it goes to a handler as a referral, with a payout of zero and the reason the check gave, and the claim agent never works it. Each claim's steps start with the check's result. The check's cost is part of the claim's cost, and a claim is checked once, not again when it carries on or is signed off. The check is the security team's, and the improver cannot change it. CLM-1901, a stolen watch whose story carries such an instruction, is in the queue to show it.

## The context layer

The agent works from the business's own data, held in a context layer: what the data means, the terms the policy wording defines, each plan's limits, waiting periods and deductible, the rules claims operations applies to every claim, outside facts such as named storms, strikes and product prices, and the policy wording and the claims manual by numbered section. Each file names the system it comes from, its owner and when it was last reviewed, and every answer the agent gets says where it came from. Data governance owns the files, and the agent only reads them. The payout rules and the approval limit stay in the app.

## The improver

The claim agent's instructions, model and reasoning effort are one configuration, kept in versions; version 1 is the agent as it was. A dispatch and an evaluation record the version they used. An improver agent follows a recipe, itself kept in versions, to improve the configuration in rounds. It reads the claim agent's results, proposes a change, waits for a handler to approve it, has the new version evaluated, and proposes a new recipe, which a handler approves in the same way. Nothing it proposes takes effect until a handler approves it. The backend keeps or rolls back each new version by the business objectives, the noise and the tolerance. Only one round is open at a time, a round works to the settings as they stood when it started, and a round stopped before its verdict leaves the current version as it was. The improver cannot change the objectives, the noise and tolerance, the spending limit, the models allowed, the approval limit, the evaluation sets or the judge.

A judge grades each explanation in an evaluation against the handler's reason, from F to A, and says whether it gave the same grounds and the same section. Each round has a spending limit that covers the improver's model calls, its evaluations and the judge.

## What the team needs to see

- The queue, with where each claim stands: waiting, in progress, waiting for sign-off or decided.
- Each claim in full, with the agent's decision and its reasons.
- What the agent is doing on a claim while it works, step by step.
- What each claim cost to work, in model cost and time, and the totals for each dispatch.
- How well the agent is doing: on a Scoreboard, evaluations on our two labelled sets, the evaluation set and the held-out set, each whole or just its five `tiny` claims. Each shows how often the agent agrees with our handlers, how much its mistakes would cost, how many claims go straight through, and what a claim costs and how long it takes, with each claim's decision beside the handler's.
- The Improvement page: where a round has got to as it happens, the proposal waiting with what it changes, the rounds so far with their scores before and after, the verdict and the cost, a chart of each version's held-out accuracy and grade, and the recipe's versions.
- The Configuration page: the current version and every version with its held-out scores, and what any version changed from the one before.
- The Settings page: the approval limit, the business objectives, the noise and tolerance, the spending limit for each round, how many claim agents work at once in the improver's evaluations, and the models allowed. A senior handler can change each, and each change records who and when. The appearance, light, dark or the computer's, is kept by each browser.
- The judge's grade for each claim of an evaluation, with the two checks, and the average grade on the Scoreboard.

## Rules

- A payout over the approval limit, $1,000 to start with and a setting, needs a handler's sign-off. The agent can approve such a claim, but the payment waits until a handler signs off. The system must block the payment until then, even if the agent tries to pay.
- Decisions follow the policy wording.
- Our handlers' own decisions on these claims are in `data/evals/`. We use them to check the agent's work in evaluations, which work copies of the claims that never show in the queue and can't be signed off. The claim agent must never see them. The improver reads the evaluation set's decisions and reasons, nothing in the agent reads the held-out set's, and the dashboard shows both sets' decisions as it does today.
- Amounts are in US dollars.

## Our records

Everything starts in `data/`, described in `data/README.md`, and is then kept in our database: the claims queue, the policies, the customers, the plans, the handlers, the policy wording and the claims manual. The held-out claims in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- No real payments.
- No messages to customers.
- Rejecting a held payout. A handler can only sign off.
