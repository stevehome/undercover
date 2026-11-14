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
- **Outcomes:** see the data check below. In short, case-level outcomes are not openly published in the way the Ombudsman's decisions are. Synthesised cases with a rule-derived answer key are credible for the calculable part, because the rules are mostly arithmetic on distance and delay plus an exceptions list.
- **Data to link:** flight delay data (free for the US, mostly paid at flight level for Europe) and historical weather. The agent can check whether a "weather" excuse matches the actual weather.
- **Buyer:** claim-management companies and airline customer-relations teams.
- **Why it fits:** it sits next to travel insurance, so the existing domain knowledge is reusable.

**Data check (14 November 2026, a light look at search results and not the full pages, so confirm each lead before relying on it).**

| Need | What exists | Verdict |
|---|---|---|
| Rules | The EU261 and UK261 regulations and the Court of Justice's case law | Public |
| Case-level outcomes | Aggregate statistics only. The UK CAA publishes passenger complaints data, and AviationADR and CEDR publish reports with counts by type (for example about 18,000 delay-compensation complaints a year at AviationADR). The Commission's enforcement reports are aggregate, and a UK government comparison says national data is inconsistent. | **The gap.** No searchable database of decisions like the Ombudsman's was found. Whether AviationADR or national bodies publish individual decisions is unconfirmed. |
| Flight delay data | US: the Bureau of Transportation Statistics on-time database is free, flight-level, with delay-cause categories, but EU261 mostly does not cover US domestic flights. Europe: Eurocontrol publishes airport-level and delay-code (CODA) data. Flight-level history is a paid product, for example OAG. | Free for the US, paid for Europe |
| Weather | Public (see the sports section) | Fine |

What this means:

- **No ready-made answer key.** Idea 1 worked because decisions with outcomes are published. Here labels would have to be built.
- **Most of the decision is calculable.** Eligibility follows distance, delay length and the airline's reason, and the compensation bands (EUR 250, 400 and 600) come from distance. Labels for that part can be generated from the rules, which gives a consistent but circular test.
- **The disputed part is the hard part.** "Extraordinary circumstances", such as weather or air traffic control, is where claims are contested. Evidence is the airline's delay code and the weather. Labels would come from Court of Justice rulings, which are few, plus a small expert-labelled set.
- **A different shape from idea 1.** Predicting an outcome from text topped out at about 75% in the first experiment and more text did not help. This idea suits an agent that checks facts with tools, such as the flight record and the weather, and then calculates the compensation. That fits the UnderCover agent's design better than a text classifier does, and the compensation amount is a richer target than upheld or not.
- **Cheap checks to do later:** whether AviationADR or the national enforcement bodies publish individual decisions, and how many Court of Justice rulings on extraordinary circumstances are available.

Sources: the CAA passenger complaints data page, AviationADR's bi-annual report 2024 to 2026, the UK government's "international comparisons of EU Regulation 261 enforcement", the BTS "airline on-time performance and causes of flight delays" page, Eurocontrol Data Snapshot #20, and OAG's historical flight data page.

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

### The oracle test: does the policy wording matter?

The improver loop left accuracy at about 75%. One untested explanation was that the complaint text lacks the evidence a decision turns on, such as the policy wording. We tested it with the best case for that explanation (`data/ombudsman/oracle.py`).

- **Method.** For each held-out decision, an extraction step copied the policy passages that the ombudsman's reasoning quotes, word for word. Each piece was checked to appear verbatim in the decision, and any piece with verdict wording was dropped. The model then scored each case twice without the clause and twice with it.
- **Coverage.** 231 of the 683 held-out cases quote policy wording (149 not upheld, 82 upheld). In a 30-case check before filtering, the model found no quoted policy wording in 15 decisions, and some passages it returned were not word for word and were trimmed or dropped. The median clause is about 180 characters.
- **The clause is a hint.** The ombudsman quotes the term that decides the case, so this is an upper bound for what policy wording could add, and not a fair test of a product.

| | Without the clause | With the clause |
|---|---|---|
| Accuracy (mean of two runs) | 74.9% | 71.9% |
| Upheld cases caught | 42.7% | 45.1% |

The clause made 20 cases better and 30 worse (sign test p = 0.20), so there was **no gain**, and the dip is not statistically real either. **Missing policy wording does not explain the plateau.** Caveats: the clauses are fragments and not whole policies, the subset leans towards not upheld (65%), a quoted clause is often an exclusion and may push the model towards "not upheld", and only one model and two runs per condition were used.

**Reading so far.** Rules, similar cases, prompt and model changes, and the decisive clause all leave accuracy at about 75%. The most likely remaining explanation is that the outcome turns on judgement calls and on facts the complaint text does not show, such as medical evidence and what the insurer actually did. Treat about 75% as close to the ceiling for predicting the plain outcome from the complaint text on this data. This is an inference from four negative results, not a proven limit.

### Limits

- **Memorisation is only partly tested.** These decisions are public, so the model may have seen some. A probe on the first 296 decisions gave the model only a reference number, firm and date and asked for the outcome. It scored 48.3% (chance on a balanced set), answering "not upheld" 88% of the time, while the firm's usual outcome alone scored 64.2%. So the model does not recall outcomes by reference. The probe does not rule out recognising a complaint from its full text, and only one model was probed. On the 683 cases, full-text accuracy was lowest for 2024 decisions (70%) and higher for 2025 (78%) and 2026 (80%), the opposite of what memorising older decisions would give. The model was released a week after the newest decision, so no case is clearly newer than its training.
- **Margin.** At 683 cases a gain of less than about 4 points cannot be told from noise.
- **Narrow search.** Three models and instruction rewrites were tried. A larger model, giving the agent the policy documents, and changes to how it reads the complaint were not.
- **Run-to-run variation.** Identical runs differ by 0.5 to 1.5 points on the held-out set (74.5%, 75.0% and 75.8% for the same no-rules setup), so quote about 75% and not a decimal.
- **Complaint wording.** The cases are reconstructed from the decision's own account of the facts, written by the ombudsman after the event, so they are cleaner than a real inbound complaint.
- **One sector.** Only travel insurance was tested.

### What it means for the product

The plain outcome is not solved: about a quarter of decisions are wrong and about 40% of upheld complaints are missed. But rules text, similar past cases and an improver loop over the model, effort and prompt all left it at about 75%. Two things follow.

- **The plain outcome is a weak target for the improver.** On this text it did not find a gain, and even the decisive policy clause did not help, so more evidence of that kind is not the answer. A result that cannot be improved cannot show the loop working, so the loop needs a task with room to move.
- **The outcome alone is probably not the product.** The value would be in what a decision needs around it:
  - the redress amount and interest,
  - which rule or term decides the case,
  - spotting the firm's own errors and settling before a complaint escalates,
  - a reason a complaints handler can check.

These need richer labels than upheld or not, and the decisions contain them (the "putting things right" sections).

### Next steps, in order

1. **A different target.** Stop working on the plain outcome. Predict the redress amount or the deciding rule from the complaint text, and run the improver loop on that, where the labels are richer and the plateau may not apply.
2. **Check the evidence idea differently.** The oracle test used only quoted fragments. A fuller test would give the model the whole policy booklet, which means collecting real booklets and matching the version in force. Do it only if the redress work suggests wording matters.
3. **Content memorisation check.** The reference-number probe found no recall. The remaining test is to rerun on decisions published well after a model's training cutoff, which needs a model released before a batch of new decisions.
4. **Another sector.** Repeat on a second product type to see whether 75% is specific to travel.

Reproduce with `uv run --env-file .env data/ombudsman/baseline.py`, `distil_rules.py`, `similar.py`, `memorisation.py`, `improve_loop.py` and `oracle.py` (`extract`, then `test`). `baseline.py` and `similar.py` take `--strip`, and `baseline.py` takes `--rules FILE`. The scripts and data are in the ignored `data/ombudsman/` folder, so they are not in the repo.

## Recommendation

1. **Build idea 1 (financial complaints) as the second product, aimed at more than the plain outcome.** It has the strongest public labels, the closest decision shape, and a buyer who already pays people to do this by hand. A plain model gets about three in four outcomes right, but nothing we tried moved it, so the product value is more likely in the evidence given to the model and in richer targets such as redress and the deciding rule.
2. **Keep idea 2 (flight delay) as the insurance-adjacent follow-up, behind idea 1.** It shares the travel domain, gives a clear weather-linked story, and suits an agent that checks facts with tools. Its data is thinner: no open case-level outcomes were found, so labels would be rule-derived, with a small expert-labelled set for the disputed cases. Check for published decisions before committing.
3. **Run a small sports forecasting experiment alongside**, only as a test bed for the improver loop. Score it against closing odds, and do not offer it as advice.

The first step for idea 1 has been done (see above): a plain model reaches about 75% from the complaint text against 51% for guessing, on 683 held-out cases. Rules and similar cases did not help. An improver loop over the model, effort and prompt did not beat it. Giving the model the policy clause the ombudsman relied on did not help either. The next step is to aim at redress and the deciding rule instead of the plain outcome, and then to write a plan in `docs/PLAN_<NAME>.md` if that shows a gain.
