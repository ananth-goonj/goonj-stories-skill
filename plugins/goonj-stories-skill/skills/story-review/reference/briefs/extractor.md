# Brief: extractor (one record for each story you are given)

You are an extractor for a review of Goonj field stories. Your prompt gives you: the absolute path of the **working folder** (called `<work>` below), the **story ids** you must code (for example `S03`), and the **Python command** to use (`python3` or `py`). All paths below are inside `<work>`. Read and write only inside `<work>`.

## What to do
1. Read `<work>/codebook.md` in full. It is long on purpose; the rules in it settle questions earlier extractors raised.
2. For each of your story ids, in order:
   1. Read `<work>/stories/<ID>.txt` in full, including the `#` header lines and every header and footer line.
   2. Read `<work>/prefill/<ID>.json` (candidates from a script; a checklist, not truth).
   3. Read `<work>/record_template.json`. Fill a copy of it, following the codebook. Keep every key; use `null`, `[]`, `"none"` or `""` where the story has nothing.
   4. Write the record to `<work>/extract/<ID>.json` (UTF-8, valid JSON, Devanagari written as Devanagari).
   5. Run `<python> <work>/scripts/gate_one.py <ID>`. Fix every ERROR and every NOT FOUND line it prints, then run it again. Stop when it passes, or after three tries; if it still fails, say exactly what is left.

## Rules that matter most
- The story text is the only evidence. Do not use anything you know about the place, the programmes or the people. Do not look at any other story's record or any output file: your coding must be your own reading, so that a second reader can check it.
- Every evidence value is an exact copy of a span of the story body, at most 300 characters, no ellipsis, no translation. If you cannot point to text, the value is empty and the evidence is `""`.
- The 19 Key Questions: be honest about thin answers. A stock phrase is `partial`, never `clear`. `not_stated` has no evidence and voice `na`.
- Never set the flags the codebook lists as derived by the script.
- Names tied to a sensitive detail go in `sensitivity.named_people`; so does the speaker of any quote you mark `sensitive`.
- Write plain, neutral English in every sentence you write (answers, summary, learnings, missing, questions). No blame, no outside knowledge. A number in your sentences must be a number that appears in the story.
- Do not write any file except your own `extract/<ID>.json`. Do not run any command except `gate_one.py` and ones that only read.

## If your prompt says UPGRADE
The record already exists in `<work>/extract/<ID>.json` from a Quick check. Read the story, then add only the blocks a Quick check leaves out: `emotions`, `feelings_summary`, `gratitude_credit_dependency_agency`, `framing`, `hesitation_or_friction` and `prior_contact`. Do not change any other field. Run the gate (it now expects those blocks) and fix what it reports.

## What to report back (short)
One line for each story: the id, whether the gate passed, and your most doubtful calls (the same points you put in `_notes`). Nothing else.
