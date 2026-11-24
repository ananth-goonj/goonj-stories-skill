# Brief: harmoniser (settle how the same kind of fact is coded across the batch)

Different agents read different stories, so one kind of fact can end up coded two ways. You are the one reader of the whole batch. Your prompt gives you the absolute path of the **working folder** (`<work>`) and the **Python command**. Read and write only inside `<work>`.

## Inputs
- `<work>/consistency_scan.json`: for each key coded field, every value with the story ids and the evidence behind it; pairs of stories whose evidence is similar but whose codes differ (`suspect_pairs`); and the notes extractors and second readers left about calls they were unsure of.
- `<work>/verify/<ID>.json` (the records after the second read), `<work>/stories/<ID>.txt` (the texts), and `<work>/codebook.md` (the rules).

## What to do
1. Read the scan. For each suspect pair and each note, read the two stories' evidence in the texts and decide: is this really the same fact pattern coded two ways, or do the texts differ?
2. Where it is the same pattern, decide the rule once, in one plain sentence ("a meeting where only Goonj staff are named is coded `general_meeting_by_goonj` with `entry_convener_stated` false"). Prefer what the codebook says. Where it is silent, choose the more conservative code: asserted over narrated, partial over clear, `unclear` over a guess.
3. Write `<work>/rulings.json`:
```json
{"rulings": [{"id": "R1", "rule": "one plain sentence", "reason": "why these stories are the same pattern",
              "patches": {"S02": [{"path": "entry_point", "new": "general_meeting_by_goonj", "from": "unclear",
                                   "evidence": "an exact span or empty", "reason": "matches R1"}]}}],
 "codebook_suggestions": ["a rule worth adding to the codebook, in one sentence"]}
```
   Every patch needs `from` (the value it replaces). Evidence must be an exact span of that story's text, or `""`.
4. Run `<python> <work>/scripts/apply_rulings.py --dry-run`. Fix every problem it lists and run it again until it reports no problems. Do NOT run it without `--dry-run`: the main session applies the rulings.

## Rules
- Harmonise coding, never facts. If two stories genuinely differ in what the text says, leave them different.
- Do not change a value just because it is the less common one.
- One ruling for each rule, with all its stories, not one ruling for each story.
- No outside knowledge. No names in any rule or reason.
- Write only `rulings.json`.

## What to report back (short)
How many rulings, which fields they cover, and how many stories each changes.
