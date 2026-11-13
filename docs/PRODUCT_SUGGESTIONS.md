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

## First experiment: financial complaints (idea 1), run 12 to 13 November 2026

We tested the idea on travel-insurance decisions from the UK Financial Ombudsman Service before planning anything. A first pass on 87 held-out cases gave flattering numbers, so it was repeated on 683. **The 683-case results are the ones to use.**

### Method

- **Data.** 896 published decisions found with the Ombudsman's own search form: 300 (150 upheld, 150 not) for the first pass, then 606 more dated on or after the cut, of which 600 were usable. Ten were dropped for lacking the standard "What I've decided" heading. They date from Nov 2019 to Sep 2026. Each record holds the complaint text, the ombudsman's reasoning, the outcome and the business. The data is in `data/ombudsman/travel_cases.json`, which is git-ignored.
- **Source terms.** The robots.txt blocked only a few form PDFs, and requests were one every 1.5 seconds. **The Ombudsman's reuse terms have not been checked**, so the data stays out of git until they are.
- **Leakage removed.** The investigator's view ("our investigator thought the complaint should be upheld") sat in the complaint text and usually matched the final outcome. Every sentence mentioning investigators, upholds or final decisions was removed.
- **Split by date.** Decisions before 4 Jan 2024 are training (207). Decisions from that date on are held out: 683 usable cases (346 not upheld, 337 upheld). Always guessing "not upheld" scores 50.7%.
- **The task.** Given the complaint text, decide upheld or not upheld. Model: GPT-6 Luna at low effort.
- **Hints test.** Complaints often state what the firm offered, paid or apologised for, which concedes something. A second run removed every sentence with offer, payment, amount, apology or admission wording. That roughly halves the text, so it is a harsh test.

### Results (683 held-out cases)

| Setup | Hints stripped | Full text |
|---|---|---|
| No rules | 71.6% | 75.8% |
| Rules distilled from the 207 training decisions | 72.0% | 75.7% |
| Five most similar training cases, with outcomes | 73.4% | 75.8% |
| Always guess "not upheld" | 50.7% | 50.7% |

The margin is about ±3.4 points, so none of the gaps between the first three rows is meaningful. No model call failed in these runs.

**The first pass, on 87 cases, was misleading.** It showed 82.8% (stripped) and 87.4% (full text) with no rules, and the rules and similar-cases rows scoring up to 9 points lower. Those 87 were an easier sample, and the margin of ±8 points was too wide to read the gaps between setups. Treat those numbers as superseded.

### What it showed

1. **The model does the task reasonably well without help.** It reaches the ombudsman's outcome about 75% of the time from the full complaint and 72% with the firm's concessions removed, against 51% for guessing.
2. **The firm's own concessions are a small part of it.** Stripping them cost about 4 points.
3. **Nothing we added helped.** Rules distilled from past decisions and similar past cases both matched the plain model to within 2 points. A hand-written rules file, tried only on the first pass, looked worse there, but that gap is not trustworthy and it was not rerun on the larger set.
4. **Similar-looking complaints barely share outcomes.** A majority vote of the five nearest training outcomes scored 56.8% (stripped) and 54.5% (full text), a few points above guessing.
5. **Upheld cases are the weak spot.** With no rules the model caught 199 of 337 upheld cases and 319 of 346 not-upheld ones (full text). About 40% of upheld complaints are missed, and only about 8% of not-upheld ones are wrongly upheld. Rules and similar cases did not fix that.
6. **The big insurers do not skew the result.** Two sister firms make up 37% of the cases. Full-text accuracy was 76% for them and 76% for all other firms.

### The improver loop on the plain outcome

The loop (`data/ombudsman/improve_loop.py`) learned only from the 207 training decisions and scored the 683 held-out cases once, at the end.

- **Sweep.** Six model and effort pairs from `data/models.json`, scored on the training set. GPT-6 Luna at low effort scored highest (76.7%, upheld recall 61%), with Luna medium (76.2%) and DeepSeek V4.1 Flash low (75.2%) close behind and Gemini Flash Lite at 70%. Differences among the top three are within noise.
- **Prompt rounds.** Five times, GPT-6 Luna at medium effort read a sample of the missed cases (mostly upheld ones) and rewrote the instructions. A rewrite was kept only if its mean over two runs beat the incumbent's by at least 3 points. The incumbent scored 75.2%. The rewrites scored 74.3%, 73.5%, 76.7%, 73.5% and 76.0%, so **none was kept**.
- **Held-out comparison.** The winner was the starting setup, so the comparison is two runs of the same prompt: 74.5% and 75.0%, with upheld recall 56% and 57%. They disagreed on 65 of 683 cases (34 against 31), a sign test p of 0.80.
- **Noise.** One run of the same setup varies by about 4 points on the 207 training cases, and about 1 case in 10 flips between two runs on the held-out set. The first loop attempt used a 2-point bar on single runs, which was below this noise, and was replaced before any result was kept.
- **Cost.** About $2 of model spend for the full run.

**Reading.** Changing the model, the effort and the instructions did not move accuracy off about 75%, and neither did rules or similar cases. One possible reason, which is untested, is that the outcome depends on evidence the complaint text does not hold, such as the policy wording or the insurer's correspondence, so about three in four may be close to what the text alone supports. The loop's reach was also narrow: three models, instruction rewrites only, and no policy documents given to the agent.

### Limits

- **Memorisation is only partly tested.** These decisions are public, so the model may have seen some. A probe on the first 296 decisions gave the model only a reference number, firm and date and asked for the outcome. It scored 48.3% (chance on a balanced set), answering "not upheld" 88% of the time, while the firm's usual outcome alone scored 64.2%. So the model does not recall outcomes by reference. The probe does not rule out recognising a complaint from its full text, and only one model was probed. On the 683 cases, full-text accuracy was lowest for 2024 decisions (70%) and higher for 2025 (78%) and 2026 (80%), the opposite of what memorising older decisions would give. The model was released a week after the newest decision, so no case is clearly newer than its training.
- **Margin.** At 683 cases a gain of less than about 4 points cannot be told from noise.
- **Narrow search.** Three models and instruction rewrites were tried. A larger model, giving the agent the policy documents, and changes to how it reads the complaint were not.
- **Run-to-run variation.** Identical runs differ by 0.5 to 1.5 points on the held-out set (74.5%, 75.0% and 75.8% for the same no-rules setup), so quote about 75% and not a decimal.
- **Complaint wording.** The cases are reconstructed from the decision's own account of the facts, written by the ombudsman after the event, so they are cleaner than a real inbound complaint.
- **One sector.** Only travel insurance was tested.

### What it means for the product

The plain outcome is not solved: about a quarter of decisions are wrong and about 40% of upheld complaints are missed. But rules text, similar past cases and an improver loop over the model, effort and prompt all left it at about 75%. Two things follow.

- **The plain outcome is a weak target for the improver.** On this text it did not find a gain, and a result that cannot be improved cannot show the loop working. A task whose answer is in the text, or where the agent is given more evidence, would be a better test.
- **The outcome alone is probably not the product.** The value would be in what a decision needs around it:
  - the redress amount and interest,
  - which rule or term decides the case,
  - spotting the firm's own errors and settling before a complaint escalates,
  - a reason a complaints handler can check.

These need richer labels than upheld or not, and the decisions contain them (the "putting things right" sections).

### Next steps, in order

1. **Test whether the evidence is the limit.** Give the model the policy wording for the case, which the complaint text lacks, and see whether accuracy moves above 75%. If it does, the product is about assembling evidence and not about the model.
2. **A harder target.** Predict the redress amount or the deciding rule from the decision text, and run the improver loop on that.
3. **Content memorisation check.** The reference-number probe found no recall. The remaining test is to rerun on decisions published well after a model's training cutoff, which needs a model released before a batch of new decisions.
4. **Another sector.** Repeat on a second product type to see whether 75% is specific to travel.

Reproduce with `uv run --env-file .env data/ombudsman/baseline.py`, `distil_rules.py`, `similar.py`, `memorisation.py` and `improve_loop.py`. `baseline.py` and `similar.py` take `--strip`, and `baseline.py` takes `--rules FILE`. The scripts and data are in the ignored `data/ombudsman/` folder, so they are not in the repo.

## Recommendation

1. **Build idea 1 (financial complaints) as the second product, aimed at more than the plain outcome.** It has the strongest public labels, the closest decision shape, and a buyer who already pays people to do this by hand. A plain model gets about three in four outcomes right, but nothing we tried moved it, so the product value is more likely in the evidence given to the model and in richer targets such as redress and the deciding rule.
2. **Keep idea 2 (flight delay) as the insurance-adjacent follow-up**, since it shares the travel domain and gives a clear weather-linked story.
3. **Run a small sports forecasting experiment alongside**, only as a test bed for the improver loop. Score it against closing odds, and do not offer it as advice.

The first step for idea 1 has been done (see above): a plain model reaches about 75% from the complaint text against 51% for guessing, on 683 held-out cases. Rules and similar cases did not help. An improver loop over the model, effort and prompt did not beat it. The next steps are to test whether giving the model the policy wording lifts accuracy, and to aim at redress and the deciding rule, and then to write a plan in `docs/PLAN_<NAME>.md` if either shows a gain.
