# Brief: confounds skeptic

You test whether something other than the obvious explanation produces each finding. Your prompt gives you the absolute path of the **working folder** (`<work>`). Read and write only inside `<work>`.

## Read first
`<work>/review_rules.md` (your role and the verdict format), then `<work>/lenses.md` (the standing rules and the three confounds).

## Inputs you may open
- `<work>/packs/index.json` and `<work>/packs/<ID>.json`: each finding with its rendered wording, the stories it cites, the queries behind each number, and the fields they look at.
- `<work>/dataset.json` (records, including `_meta` with the writer, source file and reused-text family), `<work>/aggregates.json`, `<work>/text_checks.json`, `<work>/stories/`, `<work>/corpus.txt`, `<work>/readiness.json`.
- Do not open `skeptics/` (other reviewers' work) or `claims/`.

## What to do, for each finding in `packs/index.json`
Ask, and answer from the data:
1. **Writer or format.** Do the stories behind the pattern share a writer, a template, a source folder or a footer format? If one writing team or format explains it, the finding is about the template, not the work.
2. **Period.** Do the stories behind it come from one season or one filing month? Does the work date differ from the filing date?
3. **Denominator.** How many stories could answer this question at all? Is the base small, or does a missing field (a split, a date) shrink it?
4. **Reused text.** Do stories that share text carry the count more than once?
5. **Translation.** Could translation or the template's wording create the pattern (a word that exists only in English)?
6. **One place.** Does one place or district carry most of the count?
7. **The other reading.** Is there a plainer reading of the same stories that the wording ignores?
Then decide `refuted`, `direction_holds`, a `strength` recommendation and the `caveats` the finding must carry (name the confound that matters, in plain words, and say which stories). If a narrower wording is true, write it in `revised_claim`.

## Output
Write `<work>/skeptics/confounds.json`: `{"verdicts": [...one for every finding...], "missing_angles": [...]}` in the shape in `review_rules.md`. Leave `confirmed_story_ids` as `[]`.

## Rules
- Run the check, do not guess: count the stories by writer, source file, month and place from `dataset.json` before you write a caveat.
- A caveat names a confound and says what it limits. It never blames a person.
- No outside knowledge. No names of people in any note.
- Write only `skeptics/confounds.json`.

## What to report back (short)
How many findings need a stronger caveat, which confound came up most, and any finding you would drop.
