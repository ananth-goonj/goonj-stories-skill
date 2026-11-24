# Review rules: the three skeptics, the survival rule and the editor

Every finding is tested by three reviewers who do not see each other's work. Their job is to find out whether the finding is wrong, unfair or weaker than it looks, not to be polite.

## The three roles
- **Evidence skeptic (blind).** Gets only the finding's wording, what was counted, and its caveats (`packs_blind/`). It does NOT get the queries or the story ids. It recounts from the story texts and the records on its own and writes down which stories it finds, so a script can compare its list with the computed one. It also checks that the wording is supported by what the texts actually say (search both Hindi and English).
- **Confounds skeptic.** Gets the full pack (`packs/`). It asks what else could explain the pattern: one writer or one format, the period of the work against the period of filing, a small denominator, reused text counted twice, a translation effect, one place carrying the count. It says which confound matters and what caveat the finding needs.
- **Fairness skeptic.** Reads the wording as a field team and a community member would. It looks for blame, ranking of writers or places, claims about villagers the text does not show, absence read as "did not happen", comparisons between communities, identity inferred from names, anything that points to a named person with a sensitive detail, and any tone that is harsher or kinder than the facts.

## The verdict each skeptic writes
`skeptics/<role>.json`: `{"verdicts": [...], "missing_angles": ["...", ...]}`. One verdict for every finding in the pack index:
```json
{"claim_id": "S-01", "refuted": false, "direction_holds": true, "strength": "strong",
 "confirmed_story_ids": ["S01", "S03"], "wrong_story_ids": [], "missing_story_ids": [],
 "count_corrections": [], "revised_claim": "", "caveats": ["..."], "notes": "..."}
```
- `refuted`: true only when the finding is wrong or unfair in a way no rewording fixes.
- `direction_holds`: true when the main direction is right even if details need correcting.
- `strength`: your recommendation: `strong`, `moderate`, `weak` or `drop`.
- `confirmed_story_ids`: the evidence skeptic's own list (required there; leave `[]` in the other two roles).
- `count_corrections`: plain sentences such as "the text says five stories; I find four".
- `revised_claim`: a better wording in plain English, if the finding should be narrowed or reworded. Digits are fine here: the editor turns them into placeholders.
- `caveats`: cautions the finding must carry.
- `missing_angles`: things the batch could answer that no finding covers. Not findings themselves.

## The survival rule (applied by a script, not by anyone's mood)
- A finding is **dropped** when two or more skeptics refute it, or one refutes it and none of the others says the direction holds.
- It is **contested** when exactly one refutes it but the direction holds for the others. The editor decides; the default is to drop it, and keeping it needs a written decision.
- Otherwise it **survives**.
- Its strength becomes the weakest of the author's strength and the three recommendations. Its caveats are the union of everyone's.
- If the evidence skeptic's blind list of stories differs from the computed list, the finding is marked for a query review: the editor must fix the query or write why the computed list is right.

## What the editor may and may not do
The editor writes `claims/claims_final.json`: every finding the reviewers saw, with a status `keep`, `narrowed` or `dropped`.
- It may reword a finding (keeping every number as a placeholder), narrow it to fewer stories, carry in reviewer caveats, and drop it.
- It may not keep a finding the reviewers dropped, add a finding they never saw, cite stories they did not check, give a finding more strength than they allowed, or type a number.
- Every reviewer caveat goes into `caveats`, rewritten with placeholders where it holds a number.
- A contested finding that is kept carries a `contested_decision` sentence; a finding with a query review carries a `query_review_decision` sentence. Both are plain sentences with no digits, names or placeholders.
- `finalize_claims.py` enforces all of this and runs the checker again on the final wording.

## Fairness rules that apply to everyone
Findings and reviews never rank writers, stories or places; they describe the batch. Gaps are gaps in the write-up. Names of people tied to a sensitive detail never appear. Where a story is the only evidence, the finding says "one story".
