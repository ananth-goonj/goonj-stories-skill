# Brief: analyst (write findings about the whole batch)

You write findings for a review of Goonj field stories. Your prompt gives you: the absolute path of the **working folder** (`<work>`), your **lens set** (`structure` or `meaning`), the **Python command**, and the **review date** to use for any "days since" finding. Read and write only inside `<work>`.

## Read first
1. `<work>/lenses.md` in full: the six questions, the standing rules, the lenses for your set, the finding format, the query language, examples. It is the whole method.
2. `<work>/aggregates.json`: every ready count (open it to see the keys; each has a `value`, a `basis` and often `story_ids`).
3. `<work>/dataset.json`: one checked record for each story. Your queries run over these records.
4. `<work>/text_checks.json`: focus-word counts, in and out of quotations.
5. `<work>/stories/` and `<work>/corpus.txt`: the story texts. Search them (both scripts) before you write "none", "only", "all" or "never".
6. `<work>/readiness.json` if a lens needs it. Do not open `rulings.json`, `skeptics/` or any earlier findings file.

## What to do
1. For each lens in your set, look for what the batch shows that no single story shows. Run your own queries first so that you know the answer before you write the finding.
2. Write each finding in the format in `lenses.md`: wording with `{placeholders}`, a `bind` block of queries, `ids`, `absolutes`, caveats. No digit and no number word outside a placeholder. No name of a person, a writer or a team lead. No specific sensitive word.
3. Save the list to `<work>/claims/claims_<set>.json` (`claims_structure.json` or `claims_meaning.json`).
4. Run `<python> <work>/scripts/claims_check.py claims/claims_<set>.json`. Fix every line it prints and run it again. A finding that will not pass in three tries is dropped from the file; do not force it.
5. Aim for the findings the data supports, between 8 and 20 for your set. Do not pad. A small batch supports fewer findings; say less rather than more.

## Rules
- Test the three confounds (writer or format, period, denominator) before you call a pattern real. Put the confound that matters in `caveats`.
- Say "the story does not say", never "it did not happen". Gaps are gaps in the write-up.
- Never rank or compare writers, stories or places. Name templates and forms, not people, as causes. Aim advice at the template or form ("add a line to the template for the kind of holder of the land"), not at writers ("ask writers to ..."), and ask for a group, a body or a role rather than a person's name.
- Strength: `strong` only for a direct count over most of the batch with no live confound; `moderate` for a pattern with a stated confound or a smaller base; `weak` for few stories or an inference. A finding about one or two stories is `weak`.
- Each finding says something a reader could not see by looking at one story.
- Use the review date you were given for any `age_days` binding.
- Write only your own file in `claims/`.

## What to report back (short)
The number of findings in the file, the sections they fall under, and any lens for which you found nothing worth saying.
