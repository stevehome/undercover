# Product suggestions: where else the UnderCover pattern fits

## What the pattern is

UnderCover decides a **text case against a body of rules**, and it can prove how well it does that. Five parts make it work:

| Part | In UnderCover | What a new product needs |
|---|---|---|
| A case in free text | A claim | A complaint, dispute, application, incident |
| Rules to apply | Policy wording, product rules | Statute, regulator handbook, company policy |
| Past outcomes | Prior claims | Decided cases, ideally with reasons |
| An answer key | `answer_key`, the held-out set | Cases whose correct outcome is known |
| A human who reviews | The claims handler | A caseworker, adjudicator, compliance officer |

The answer key is what makes the evaluation scoreboard and the improver rounds possible. **The best next product is the one where labelled outcomes are cheapest to get.** Everything else (rules, retrieval, the dashboard, versions, rounds) carries over almost unchanged.

Dates and licences below are from memory. Check each source's current terms before building on it.

## The ideas, ranked

| # | Idea | Rules public? | Labelled outcomes public? | Synthesis needed | Fit |
|---|---|---|---|---|---|
| 1 | Financial complaint adjudication | Yes | Yes, thousands | Low | Excellent |
| 2 | Flight delay compensation (EU261 / UK261) | Yes | Partly | Medium | Excellent |
| 3 | Employment and tenancy tribunal pre-screening | Yes | Yes | Low | Very good |
| 4 | Health insurance denial appeals | Yes | Some states | Low-medium | Very good |
| 5 | Data-protection (GDPR) breach assessment | Yes | Yes (enforcement decisions) | Medium | Good |
| 6 | Internal policy compliance (expenses, procurement) | Company's own | No | All of it | Good for a demo |
| 7 | Sports and event outcome forecasting | No rules | Yes, plentiful | Low | Different shape, see below |

### 1. Financial complaint adjudication

A customer complains to a bank, insurer or broker. Someone decides whether the firm treated them fairly and what redress is due.

- **Rules:** a regulator's handbook, for example the FCA's complaint-handling and conduct rules in the UK.
- **Outcomes:** the UK Financial Ombudsman Service publishes its final decisions online, each with the outcome (upheld or not) and its reasoning. Other ombudsman schemes do the same.
- **Synthesis:** minimal. Use the published decision as the answer key, and have a model write the original complaint as the customer would have, from the decision's facts. Keep the real decision hidden from the agent.
- **Buyer:** firms' complaints teams, who want to know whether to settle early before the ombudsman hears it.
- **Why it fits:** the closest cousin of UnderCover. It is the same decision with reasons, and the outcome is the same kind of label.

### 2. Flight delay compensation

Did a delay, cancellation or denied boarding qualify for compensation under EU261 or UK261, and for how much?

- **Rules:** the regulations themselves and the Court of Justice's case law, for example on what counts as "extraordinary circumstances".
- **Outcomes:** court judgments and national enforcement-body decisions are public but scattered. Synthesised cases with a rule-derived answer key are credible here, because the rules are mostly arithmetic on distance and delay plus an exceptions list.
- **Data to link:** US Bureau of Transportation Statistics on-time data, and historical weather. The agent can check whether a "weather" excuse matches the actual weather.
- **Buyer:** claim-management companies and airline customer-relations teams.
- **Why it fits:** it sits next to travel insurance, so the existing domain knowledge is reusable.

### 3. Employment and tenancy tribunal pre-screening

"Does this dispute have a realistic chance, and under which rule?"

- **Rules:** employment and landlord-tenant statutes, tribunal procedure rules.
- **Outcomes:** the UK's National Archives "Find Case Law" service and the gov.uk employment tribunal decisions are searchable. Canada's CanLII and BAILII cover other jurisdictions. Terms vary, so read each licence.
- **Buyer:** legal-aid charities, union advice lines, small-firm solicitors triaging inbound enquiries.
- **Risk:** the output is close to legal advice. Position it as triage for a human adviser, never as the final word.

### 4. Health insurance denial appeals

A patient's claim was denied. Was the denial consistent with the plan and with medical-necessity criteria?

- **Outcomes:** some US states publish independent medical review decisions with the outcome. California's regulator is the one I would check first.
- **Rules:** the plan documents and published clinical criteria.
- **Risk:** health data and medical judgement raise the bar for review. Use only the public decisions at first, with a human clinician always in the loop.

### 5. Data-protection breach assessment

Given an incident description, does it breach GDPR, must it be reported, and what is the likely penalty band?

- **Rules:** the regulation text and the European Data Protection Board's guidance.
- **Outcomes:** public enforcement decisions, and community trackers that collect the fines and the articles breached.
- **Buyer:** data-protection officers who must decide within 72 hours whether to notify.

### 6. Internal policy compliance

"Does this expense claim, purchase request or contract clause follow company policy?"

- Nothing public, so everything is synthetic: write a policy, generate cases that clearly comply, clearly break it, and sit on the boundary. The answer key comes from how each case was built.
- Good as a fast demo or a first pilot with one design partner, because they will have real policies and real past decisions you could use under an agreement.

## Sports and event forecasting

This is a different product, and I would be honest about three differences.

1. **There are no rules to apply.** The outcome comes from form, not from reading a rulebook. A language model adds little over a statistical model on the numbers. It can add something by reading **text** that the numbers miss: injury reports, team news, press conferences.
2. **The market is already a strong baseline.** Bookmakers' closing odds are well calibrated. Beating them is hard, so the honest target is "as good as the market, with reasons", scored with log loss or Brier score against closing odds.
3. **Betting advice is regulated.** A tipster product invites licensing and consumer-protection problems.

What does fit UnderCover well is the **evaluation loop**. Results arrive every week with no labelling cost, so the improver can run rounds against a steadily growing answer key. That is a better test bed for self-improvement than any legal corpus.

**Data that is public, at least for research use:**

- Football: football-data.co.uk (results and odds by league and season), StatsBomb's open event data.
- American football: the nflverse project (play-by-play, schedules).
- Tennis: Jeff Sackmann's match data on GitHub (non-commercial licence, so not for a paid product).
- Weather: Open-Meteo's historical archive (free, hourly, by coordinates), NOAA and national met services.

**Where it becomes a business is next to insurance, not betting:**

- **Event cancellation and parametric cover.** "Will this outdoor event be rained off?" has a clear weather trigger, public weather data and a defined payout. It extends UnderCover's own domain.
- **Flight delay prediction** from weather and airport data, which feeds idea 2 and could set the price of delay cover.
- **Fantasy sports and club analytics**, where the buyer wants explained predictions.

## Getting data when it isn't public

1. **Start from a real decision, hide it, write the case.** A model writes the complaint or claim from the decision's facts. The real outcome is the answer key. This keeps the labels true even though the case text is new.
2. **Split by date, not at random.** Train on older decisions and hold out the newest ones. Otherwise the agent may simply have seen the case during its own training.
3. **Check for leakage.** A synthetic case that names the statute section or quotes the verdict makes the task too easy. Strip those and sample some by hand.
4. **Add hard cases on purpose.** Real decisions skew towards the clear ones. Generate boundary cases from the rules, and have an expert label a small set.
5. **Keep a small human-labelled set** as the held-out set that the improver never sees, as UnderCover does now.

## What carries over from UnderCover

Most of the build does not change: the claim agent graph, the dispatcher and swarm, the evaluations and scoreboard, versions and the improver, the handler review screen and sign-in. What changes per product:

- the rules corpus and how it is retrieved,
- the case intake format,
- the answer key and the grading rubric (for example "outcome correct" plus "cited the right rule"),
- the review screen's wording.

## First experiment: financial complaints (idea 1), run 12 November 2026

We tested the idea on travel-insurance decisions from the UK Financial Ombudsman Service before planning anything.

### Method

- **Data.** 300 published decisions, 150 upheld and 150 not upheld, found with the Ombudsman's own search form. Four were dropped for lacking the standard "What I've decided" heading, leaving 296. They date from Nov 2019 to Sep 2026. Each record holds the complaint text, the ombudsman's reasoning, the outcome and the business. The data is in `data/ombudsman/travel_cases.json`, untracked.
- **Source terms.** The robots.txt blocked only a few form PDFs, and requests were one every 1.5 seconds. **The Ombudsman's reuse terms have not been checked**, so the data stays out of git until they are.
- **Leakage removed.** The investigator's view ("our investigator thought the complaint should be upheld") sat in the complaint text and usually matched the final outcome. 861 sentences mentioning investigators, upholds or final decisions were removed.
- **Split by date.** Decisions before 4 Jan 2024 are training (207); the rest are held out (89, of which 87 were long enough to use).
- **The task.** Given the complaint text, decide upheld or not upheld. Model: GPT-6 Luna at low effort. Always guessing "not upheld" scores 55.2%.
- **Hints test.** Complaints often state what the firm offered, paid or apologised for, which concedes something. A second run removed every sentence with offer, payment, amount, apology or admission wording. That halves the median text (2,278 to 1,203 characters), so it is a harsh test.

### Results

| Setup | Hints stripped | Full text |
|---|---|---|
| No rules | **82.8%** | **87.4%** |
| Hand-written rules (a paraphrase from memory, unchecked) | 73.6% | 85.1% |
| Rules distilled from the 207 training decisions | 77.0% | 81.6% |
| Five most similar training cases, with outcomes | 81.6% | 79.3% |
| Always guess "not upheld" | 55.2% | 55.2% |

With 87 cases the margin is about ±8 points, so differences of a few points mean nothing.

### What it showed

1. **The model already does the task well.** It reaches the ombudsman's outcome about 83% of the time from the complaint alone (87% with the full text), against 55% for guessing.
2. **The firm's own concessions are not the main driver.** Stripping them cost about 5 points, and 83% is far above guessing.
3. **Nothing we added helped.** Rules, whether written by hand or distilled from past decisions, and similar past cases were all level with no rules or lower. On stripped text the hand-written rules scored 9 points lower and the distilled ones about 6 lower. Each gap is inside the margin, but all the rules runs pointed the same way.
4. **Similar-looking complaints do not share outcomes.** A majority vote of the five nearest training outcomes scored 58.6% (stripped) and 55.2% (full text), close to guessing.
5. **Upheld cases are the weak spot.** The model caught 28 of 39 upheld cases and 44 of 48 not-upheld ones (stripped, no rules). Every version with added context missed more upheld cases.

### Limits

- **Memorisation is untested.** These decisions are public, so the model may have seen some. Accuracy on 2026 cases matched older ones (88% against 84% to 91%), which is only mildly reassuring because we don't know the model's training cutoff.
- **Small held-out set.** 87 cases cannot show a gain of less than about 8 points.
- **One model, one prompt.** No other models, efforts or prompt wordings were tried.
- **Dominant firms.** One insurer is in 64 of the 300 decisions, and scores by firm are too small to read.
- **Complaint wording.** The cases are reconstructed from the decision's own account of the facts, written by the ombudsman after the event, so they are cleaner than a real inbound complaint.

### What it means for the product

Deciding upheld or not upheld is probably not the product, since a model does it well unprompted. The value would have to be in what a decision needs around the outcome:

- the redress amount and interest,
- which rule or term decides the case,
- spotting the firm's own errors and settling before a complaint escalates,
- a reason a complaints handler can check.

Those need richer labels than upheld or not, and the decisions contain them (the "putting things right" sections).

### Next steps, in order

1. **Memorisation check.** Rerun on decisions published after a model's known training cutoff, or on a model with an earlier cutoff. If accuracy falls on newer cases, the 83% is flattered.
2. **A larger held-out set.** Pull more decisions across sectors, so a gain of a few points can be told from noise.
3. **A harder target.** Predict the redress amount or the deciding rule from the decision text, and use it to give the improver rounds something to improve on. The improver loop needs a task where the plain model leaves room.

Reproduce with `uv run --env-file .env data/ombudsman/baseline.py`, `distil_rules.py` and `similar.py` (each takes `--strip`, and the first takes `--rules FILE`).

## Recommendation

1. **Build idea 1 (financial complaints) as the second product, but with a harder target than upheld or not.** It has the strongest public labels, the closest decision shape, and a buyer who already pays people to do this by hand. The first experiment showed that the plain outcome is already easy for a model, so aim at redress, the deciding rule and the reasoning.
2. **Keep idea 2 (flight delay) as the insurance-adjacent follow-up**, since it shares the travel domain and gives a clear weather-linked story.
3. **Run a small sports forecasting experiment alongside**, only as a test bed for the improver loop. Score it against closing odds, and do not offer it as advice.

The first step for idea 1 has been done (see above): a baseline from complaint text alone reaches about 83% against 55% for guessing. The next step is the memorisation check and a harder target, and then a plan in `docs/PLAN_<NAME>.md` if those hold up.
