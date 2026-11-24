# Brief: editor (final wording of the findings)

Three skeptics have tested the findings and a script has applied the survival rule. You write the final version. Your prompt gives you the absolute path of the **working folder** (`<work>`) and the **Python command**. Read and write only inside `<work>`.

## Read first
`<work>/review_rules.md` (what you may and may not do), then `<work>/lenses.md` (the finding format and the query language).

## Inputs
- `<work>/claims/claims.json`: the findings as written (wording, `bind`, `ids`, `absolutes`, caveats...).
- `<work>/claims/claims_reviewed.json`: for each finding its review status (`survives`, `contested`, `dropped`), who refuted it, the strength ceiling (`final_strength`), whether the evidence skeptic's blind story list differs (`needs_query_review`, `blind_diff`), the union of reviewer caveats, reworded versions the reviewers suggested, count corrections and notes, and the angles the reviewers say no finding covers (`missing_angles`).
- `<work>/skeptics/*.json` for the reviewers' full words. `<work>/packs/` for the rendered numbers.

## What to do
Write `<work>/claims/claims_final.json`: a list holding every finding in `claims_reviewed.json`, each a full finding object (the same fields as in `claims.json`) plus `"status"`:
- `"dropped"` with a `"drop_reason"` (one plain sentence) for every finding the reviewers dropped, and for any finding you cannot make true and fair.
- `"keep"` for a finding that survived and needs no change; `"narrowed"` when you changed its wording, its queries or its story set.
- A **contested** finding is dropped unless you can keep it: then add `"contested_decision"`: one plain sentence saying why it stays (no digits, no names, no placeholders).
- A finding marked `needs_query_review`: look at the difference. Fix the query so the computed ids match the blind list, or add `"query_review_decision"`: one plain sentence saying why the computed list is right.
- Carry **every reviewer caveat** into `caveats`, reworded in plain English with `{placeholders}` wherever the caveat holds a number.
- Where a reviewer corrected a count or suggested a better wording, apply it: change the queries or the wording, never type a number.
- Set `strength` no higher than `final_strength`. A narrower finding that cites fewer stories is fine; one that cites a story the reviewers did not check is refused.

Then run `<python> <work>/scripts/finalize_claims.py`. It runs the checker again on your final wording and enforces the rules above. Fix every line it prints and run it again until it reports no problems.

## Rules
- Do not add a finding. Do not keep a finding the reviewers dropped. Do not type a number, a number word or a name.
- Plain English a programme officer would read without help. No blame, no jargon.
- Do not edit any file except `claims/claims_final.json`.

## What to report back (short)
Kept, narrowed and dropped counts; each contested finding and your decision in one line; and the reviewers' `missing_angles` that no finding covers, so the main session can mention them.
