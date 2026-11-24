# Lenses, and how to write a finding

This is what the analysts read. A finding is a short, plain statement about the whole batch, written as a template: the words are yours, every number and story id is filled in by a script from a query you write. A checker rejects anything typed by hand.

## The six questions every finding should help answer
- **Q1 Outlook:** what does the work in these stories look like overall: places, activities, time?
- **Q2 Repeat places:** does the same place appear in more than one story?
- **Q3 Spread:** did one village's work lead another village to ask for the same?
- **Q4 Feelings and voice:** what did community members feel, and is it in their own words?
- **Q5 Reasons:** why did people choose that work, and do the stories bring the reason out?
- **Q6 Documentation:** what do the stories leave out, and what should writers be asked to include?

## Standing rules for every finding
- Numbers and story ids come from a query. Never type a digit or a number word in the wording. State the denominator and the basis in `basis` and `how_counted`.
- Before you write "none", "only", "all", "never" or "every", search the story texts (`text_checks.json` has the focus words; `corpus.txt` holds every text, so you can grep both scripts). The checker makes you bind each of these words to a count that proves it.
- Test three confounds before you call a pattern real: **template or writer** (does one writing team or format explain it?), **period** (when the work happened against when the story was filed), and **denominator** (how many stories could answer the question at all).
- A group of stories that reuse the same text counts once where it matters (`_meta.family`).
- Absence in a story is absence in the write-up, not in the village. Say "the story does not say", never "it did not happen".
- Quotes are the writer's rendering; in a translated batch every quote is the translator's.
- Identity: community labels only as the text writes them, at settlement level. Never compare communities. Never tie a named person to a menstrual, health, injury or bereavement detail; the checker refuses names and the specific words.
- The reader is the internal programme and MEL team. Plain English, no jargon, no blame. Name templates, forms and processes as causes, never people, and aim advice at the template or form rather than at writers. Never rank or compare writers or stories.
- A finding that is only a restatement of one table row is not a finding. A finding says what a reader would not see by looking at one story.

## Structure lenses (analyst set "structure")
1. **Who did the work.** Participants: totals only "as recorded"; shares only from full women/men pairs. Women who proposed against women who worked. Meeting attendance is never added to work counts. Is migration stated, and is it gendered?
2. **What was done.** The mix of works, primary against secondary, repair against new building, sizes and units, purposes named.
3. **Outcomes, evidence, timing.** Immediate, expected, and seen later (with a time marker). Season of the work. Past-tense claims that could not yet have been seen. Photos.
4. **Provenance, templates, writers.** Writer and format clusters; reused text and duplicates; codes and their formats; labelled footers; translation effects. Which format carries which fields. Frame gaps as template effects.
5. **Geography and footprint.** Districts and blocks, per-district denominators. The batch is not the programme's footprint.
6. **Repeat places (Q2).** Same village in the same district in more than one story; blocks with more than one story. Say that matching is by exact spelling.
7. **Spillover and referral (Q3).** Who carried the idea (a villager who saw it, a volunteer, a relative, an anganwadi worker, women from another ward). "Neighbours praised it" is not adoption; a volunteer referral is outreach, not spread.
8. **Reporting chain and completeness (Q6).** Gaps by writer or format (codes, dates, split, district, quotes, photos). Feeds the writer questions.
9. **Key Question coverage.** For each group (What, Why, Who, Where, When, How) and each question: how many stories answer clearly, in part, or not at all. The weakest questions. Which tags dominate a question.
10. **Contributions and ownership.** What people put in besides labour, and who gave it; the upkeep arrangements (pledge, arrangement, appeal to authority).

## Meaning lenses (analyst set "meaning")
11. **Entry, facilitation, decision.** How Goonj came in; whether the text says who convened the meeting; how much of the team's method is described; decision narrated or asserted; who is the grammatical decider.
12. **Voice and vocabulary.** Quotes on three thresholds: strict (named resident, direct quote), moderate (plus unmarked direct speech), generous (any attributable line). Who is quoted instead of the people who did the work. Women quoted against women working. Frame words and whose mouth they are in.
13. **Exchange, kit, dependency.** Kit mentioned? Framing (gift, unframed, exchange, dignity). Dependency against credit against gratitude against agency, by voice. Is the kit the motive?
14. **Sensitivity and consent.** Named disclosures, minors, identity labels, reused testimony; the consent register (counts and tiers only).
15. **Need to choice (Q5).** Is the reason stated, in whose voice, before the decision or only afterwards? Who proposed it, what triggered it? Does the stated need fit the chosen work? Programme-menu agendas against community agendas. Prior attempts. Options weighed. A stock phrase such as "everyone decided together" is a writing formula, not evidence of a process.
16. **Feelings and voice (Q4).** Feelings before, during and after; classes; whose feeling; own words against the writer's; stock closing lines; shifts for the same holder; hesitation and friction. Are feelings brought out, or asserted in closing lines?
17. **Framing, identity, dignity.** Deficit against agency language and whose voice carries it.

## The finding format
One JSON object. A file holds a list of them.

| field | what it is |
|---|---|
| `id` | a short unique id; use `S-01`, `S-02` for the structure set and `M-01`, `M-02` for the meaning set |
| `section` | where it appears in the report: `outlook`, `who`, `why`, `entry`, `contrib`, `change`, `voice`, `exchange`, `format` or `consent` |
| `answers` | which of Q1 to Q6 it helps answer, e.g. `["Q1", "Q6"]` |
| `strength` | `strong` (a direct count over most of the batch, no confound), `moderate` (a pattern with a stated confound or a smaller base), `weak` (few stories, or an inference) |
| `text` | one or two plain sentences with `{placeholders}` |
| `basis` | optional: the numbers and denominators, again with placeholders |
| `bind` | the queries behind each placeholder (below) |
| `ids` | the names of the bindings whose stories the finding rests on; the script takes the union as the story list |
| `absolutes` | one entry for every "all", "none", "only", "never", "every", "no story" in the wording |
| `caveats` | at least one for `moderate` and `weak`: the confound, the denominator, the limit |
| `implication` | what it means for the programme or the format |
| `suggested_use` | what a reader could do with it. It is advice, so a number word or "every" is allowed here; a digit, a name or a sensitive word still is not |
| `how_counted` | one plain sentence: what was counted, over which stories |

### Placeholders
`{name}` prints a value; `{name:stories}` prints it with a unit and the right singular or plural ("1 story", "5 stories"; `{name:times}` gives "1 time", "13 times"). `{N}` is the number of stories in the batch. Write each sentence so that it reads right for 1 as well as for 5: "A total is stated in {n:stories} of the {N}", not "{n:stories} give a total" (which would read "1 story give"). A placeholder must have a binding. Anything outside placeholders must contain no digit, no number word (one, two, half, both, pair...) and no undeclared absolute.

### Bindings (each returns a value and the stories behind it)
- `{"count": PRED}` stories where PRED holds. `{"ids": PRED}` the list of their ids.
- `{"count_items": {"path": "quotes", "where": PRED}}` items across stories. `{"stories_with_items": {"path": "quotes", "where": PRED}}` stories with at least one such item.
- `{"sum" | "min" | "max" | "median" | "distinct": {"path": "participants.total", "where": PRED}}`.
- `{"registry": ["by_district", "value", "District A"]}` a value from `aggregates.json` (open it to see the keys).
- `{"hits": {"term": "collective", "field": "n | in_quotes | in_narration | stories"}}` a focus-word count from `text_checks.json`.
- `{"quote": {"story": "S04", "text": "an exact phrase"}}` an exact phrase from a story.
- `{"arith": "(100 * a) // N"}` + - * // on earlier bindings and `N` (whole numbers only).
- `{"age_days": {"agg": "min | max", "on": "2026-11-08"}}` days from each story's last work date to a date.

### Predicates
`{"all": [..]}`, `{"any": [..]}`, `{"not": ..}`, `{"path": "entry_point", "op": "eq", "value": "unclear"}`, `{"any_item": {"path": "quotes", "where": ..}}`, `{"all_items": ..}`. Paths use dots, `[*]` for any list item, `[0]` for an index; `_derived.flags_all` holds every derived and agent flag. Operators: `eq ne in not_in gt gte lt lte is_null not_null is_int true false empty non_empty contains matches`.

### Example 1: a count and an absolute
```json
{"id": "S-01", "section": "who", "answers": ["Q1", "Q6"], "strength": "strong",
 "text": "A total number of people is stated in {n_total:stories} of the {N} ({lo} to {hi}). No story gives a women and men split, so the batch cannot show the share of women.",
 "basis": "Stories with a total: {n_total}; with a women and men split: {n_split}.",
 "bind": {"n_total": {"count": {"path": "participants.total", "op": "is_int"}},
          "lo": {"min": {"path": "participants.total"}}, "hi": {"max": {"path": "participants.total"}},
          "n_split": {"count": {"all": [{"path": "participants.male", "op": "is_int"}, {"path": "participants.female", "op": "is_int"}]}}},
 "ids": ["n_total"], "absolutes": [{"word": "no story", "bind": "n_split", "equals": 0}],
 "caveats": ["A women-only count is a minimum, not a total."],
 "implication": "The format does not ask for a split.", "suggested_use": "Add a prompt for the split.",
 "how_counted": "Stories with a total; stories with both a women and a men count."}
```
### Example 2: a word search, in and out of quotes
```json
{"id": "M-01", "section": "voice", "answers": ["Q4"], "strength": "moderate",
 "text": "The word “collective” appears {n:times} in {s:stories}, and {q:times} of them are inside a quotation.",
 "bind": {"n": {"hits": {"term": "collective", "field": "n"}}, "s": {"hits": {"term": "collective", "field": "stories"}},
          "q": {"hits": {"term": "collective", "field": "in_quotes"}}},
 "ids": ["s"], "caveats": ["The word counts are for English and Hindi forms listed in the focus words."],
 "implication": "The framing comes from the writers.", "suggested_use": "Compare with another batch.",
 "how_counted": "A word search of every story text, inside and outside quotation marks."}
```
### Example 3: a share, written with whole numbers
`"bind": {"a": {"count": ...}, "pct": {"arith": "(100 * a) // N"}}` and text "about {pct} in every hundred stories". Do not write "%" with a typed digit. The checker allows only whole-number arithmetic, so a share is rounded down.

## The checker's messages
Run `python3 scripts/claims_check.py claims/<your file>.json` and fix each line it prints: a typed number, a number word, an undeclared absolute, a name, a specific sensitive word, a quoted phrase not in the cited stories, an unknown binding, an absolute that is false. Each finding that cannot be made to pass in three tries should be dropped, not forced.

## Exemplar passages (meaning lenses)
For each meaning lens you may add up to six exemplar passages to `claims/exemplars_<set>.json`: `{"story_id", "text" (exact), "why"}`. Never use a sensitive passage or one by a named person tied to a sensitive detail.
