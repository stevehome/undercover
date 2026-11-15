# Label spot-check: five claims

For each claim, open it in `claims.json` (and `customers.json` for claim history), read the key in `decisions.json`, and tick each line. The rules are in `data/claims_manual.md` and `data/policy_wording.md`; the limits are in `data/plans.json`. A claim passes when every box is ticked. Note anything you disagree with at the bottom.

Plan limits used below: Economy has a 12-hour trip delay wait, a $100 deductible and a $150 per-item limit. Premium has a 6-hour wait, a $50 deductible, a $300 per-item limit and a $1,500 baggage maximum. Electronics Plus raises the electronics per-item limit to $1,200.

## CLM-1413: broken ankle after a "scenic flight" (key: decline, $0)

Economy policy POL-2413, no add-ons.

- [ ] The story says sightseeing flight; the **card statement extract** shows "TANDEM PARAGLIDE BEATENBERG-INTERLAKEN" paid to Aerie Adventures on Feb 11.
- [ ] The hospital record puts the injury on landing at Interlaken from Aerie Adventures, the same day.
- [ ] Paragliding is on the adventure sports list (wording section 8), and section 7 excludes it without the add-on.
- [ ] You agree that decline is right, not refer (no document is missing and nothing contradicts the card statement).

## CLM-1416: phone taken at a hotel desk (key: refer, appears payable at $150)

Premium policy POL-2416, filed 2026-09-10, no Electronics Plus.

- [ ] `customers.json` CUS-3416 has earlier claims filed 2025-08-21, 2025-09-14 and 2026-03-04.
- [ ] Two of them (2025-09-14 and 2026-03-04) fall inside the 12 months before 2026-09-10, and the 2025-08-21 one does not, so this is the **third** claim in 12 months.
- [ ] The 2025-09-14 claim was declined, and the manual (section 9) says to count declined claims.
- [ ] A third claim goes to Special Investigations before payment, whatever its merits (section 9).
- [ ] Appears-payable amount: $640 phone capped at $300, less the $100 hotel refund (in the hotel statement), less the $50 Premium deductible = $150.

## CLM-1418: Ireland trip cancelled, son in hospital (key: refer, appears payable at $2,460)

Premium policy POL-2418, filed 2026-06-25.

- [ ] The only medical letter is signed by Dr. Laura Whitman, who says she is Owen's mother and is on the airline booking as a passenger.
- [ ] Wording section 12 says a physician cannot be a traveling companion or a family member, so there is no physician's statement.
- [ ] The manual says a missing required document means refer, not decline.
- [ ] Appears-payable amount: flights $2,340 + cottage $900 retained = $3,240, less the airline's $780 future travel credit = $2,460 (check the airline confirmation).

## CLM-1420: ferry cancelled by Storm Ysolde (key: approve, $272)

Economy policy POL-2420, bought 2026-09-01.

- [ ] The weather bulletin that names the storm is dated **2026-09-02**, the day after the policy was bought, so the storm was not publicly known at purchase and the exclusion does not apply.
- [ ] Scheduled sailing Sept 4 at 08:15, actual departure Sept 5 at 14:05: 29 hours 50 minutes, past the 12-hour Economy wait.
- [ ] Hotel $240 (under the $350 limit) + taxi $28 + meals $64 = $332.
- [ ] The $95 concert ticket is a consequential loss and is left out.
- [ ] The ferry company's $60 accommodation payment (in the cancellation notice) comes off: $332 − $60 = $272, under the $300 Economy maximum.

## CLM-1424: bag snatched in Valencia (key: approve, $1,500)

Premium policy POL-2424 with Electronics Plus.

- [ ] Snatched from the shoulder and reported to the police within the hour, so it is theft from the person.
- [ ] The smartwatch (Corvane Lumen X2, $649) and the camera (Brisa Pocket 2, $1,099) are on the electronics list, so they get the $1,200 limit and are paid in full.
- [ ] The smart ring (Vantor Halo, $449) and the handheld GPS (Quillon Wayfinder 5, $599) are not on the electronics list, so each is held to $300.
- [ ] Two t-shirts at $40 each are separate items.
- [ ] Total: 649 + 300 + 300 + 1,099 + 40 + 40 = $2,428. Less the $50 deductible = $2,378. The Premium baggage maximum is $1,500, so the payout is $1,500.
- [ ] The receipts (April 2026) come after the smartwatch's March 2026 release date in the product sheet.

## Your notes

Disagreements or doubts:
