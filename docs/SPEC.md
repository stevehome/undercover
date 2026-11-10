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

When the agent approves a payout over $1,000, it stops and waits for a handler, keeping everything it has worked out. As soon as a handler signs off on the dashboard, the agent picks the claim up from where it stopped and pays it. Between the sign-off and the payment the claim shows as in progress, and the payment records who signed off and when. If the agent isn't running when a handler signs off, the next dispatch picks the claim up. A handler can only sign off for now; rejecting a held payout comes later.

If the agent is stopped partway through a claim, by a crash, a restart or Ctrl-C, it carries on with that claim from where it got to the next time it runs, and that doesn't count as a new attempt. A claim that hits a rate limit or a timeout waits and carries on from where it got to, and if it is still hitting them it stays in progress for the next dispatch. A claim that fails with any other error goes back in the queue and the same dispatch tries it once more, and a claim that fails twice is left for a handler. One bad claim never stops a dispatch. A dispatch that was stopped is finished by the next one. No claim is ever decided or paid twice.

## What the team needs to see

- The queue, with where each claim stands: waiting, in progress, waiting for sign-off or decided.
- Each claim in full, with the agent's decision and its reasons.
- What the agent is doing on a claim while it works, step by step.
- What each claim cost to work, in model cost and time, and the totals for each dispatch.
- How well the agent is doing: on a Scoreboard, evaluations on our two labelled sets, the evaluation set and the held-out set, each whole or just its five `tiny` claims. Each shows how often the agent agrees with our handlers, how much its mistakes would cost, how many claims go straight through, and what a claim costs and how long it takes, with each claim's decision beside the handler's.
- The agent's instructions, read only.

## Rules

- A payout over $1,000 needs a handler's sign-off. The agent can approve such a claim, but the payment waits until a handler signs off. The system must block the payment until then, even if the agent tries to pay.
- Decisions follow the policy wording.
- Our handlers' own decisions on these claims are in `data/evals/`. We use them to check the agent's work in evaluations, which work copies of the claims that never show in the queue and can't be signed off. The agent must never see them.
- Amounts are in US dollars.

## Our records

Everything starts in `data/`, described in `data/README.md`, and is then kept in our database: the claims queue, the policies, the customers, the plans, the handlers, the policy wording and the claims manual. The held-out claims in `data/evals/` are for checking the agent later and stay out of the queue.

## Not for now

- No sign-in. Everyone who uses the screens sees everything.
- No real payments.
- No messages to customers.
- Rejecting a held payout. A handler can only sign off.
