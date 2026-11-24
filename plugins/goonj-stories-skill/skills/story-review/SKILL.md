---
name: story-review
description: Review a folder of Goonj field stories (Hindi, English or both). Asks which folder holds the stories, then reads each story, records what it says with the story's own words as proof, shows how well the stories answer the 19 Key Questions, scores readiness for outside use, lists the stories that need a consent check, and writes ranked questions for each writer. Gives an HTML report, an Excel workbook, per-story readings and a run log. Quick check or Full review (adds a second reader, batch rulings and findings tested by three skeptics). Use when someone asks to review, analyse or check a folder of stories, or wants Key Question coverage, readiness, a consent register or questions for writers.
---

# Story review

Reviews one folder of field stories the same way every time. Scripts guarantee three things: every quote in a record is an exact copy of the story text, every number in an output is computed (never typed), and names tied to a sensitive detail are withheld everywhere. Agents do the reading; scripts do the checking, counting and building.

## When to use
A folder of stories (`.docx`, `.txt`, `.md`, `.rtf`) and a request to review, analyse or check them: what they say, how complete they are, whether they are ready for outside use, whom to ask for what. Not for one story you only need summarised.

## Non-negotiables
1. **Ask which folder holds the stories before you read anything.** If the request already names it, say which folder you will use and go on. Never guess a folder.
2. **Never change the stories.** Sources are read only. Everything you write goes into a new folder (`Story Review <date>` beside the stories, or where the user says) and into its `_working` folder.
3. **Scripts own every number, quote and file.** Never type a count, a percent or a date into an output, a record or a message to the user; take it from a script's output. Never edit a record by hand to get past the gate: send it back to be fixed, because a hand edit can break the exact-quote guarantee.
4. **Privacy.** Never name a person beside a health, injury, bereavement or menstrual detail, in files or in chat. In your final message name stories by id and consent tier only, never by the type of detail. Never rank, score or compare writers or stories (readiness bands are the one per-story score, and they measure the write-up).
5. **Everything stays on this computer.** No web search, no upload, no web request. The report loads nothing from the web.
6. **Do not skip a stage or declare it done without its check.** The outputs are ready only when `verify_outputs.py` passes.
7. **Ask before anything large.** Show the estimate; warn at 30 stories, ask for a clear yes at 60, and offer a 3-story pilot.
8. **If a script cannot run, say so and stop that stage.** Do not work around a permission or sandbox block. Tell the user what is blocked and what to do.

## Words and paths
- `<skill-dir>`: the "Base directory for this skill" shown when this skill loads. Always an absolute path.
- `<py>`: the Python command. `python3` on Mac and Linux, `py` on Windows (preflight prints which works).
- `<work>`: `<output folder>/_working`. After Step 2, every script is run from `<work>/scripts/` (a copy made for this review), and every agent works only inside `<work>`.
- Reference files, read when needed: `<skill-dir>/reference/method.md` (the method), `outputs.md` (how to read the results), `pitfalls.md` (traps from earlier reviews).

## Step 0: Ask
Ask: "Which folder holds the stories?" Resolve it to an absolute path. Do not open anything in it yet.

## Step 1: Check the computer
```bash
<py> "<skill-dir>/scripts/preflight.py" --folder "<stories folder>"
```
- `NOT READY`: tell the user exactly what is missing, in its own words. On Windows say `install-requirements.bat` (at the top of the plugin folder and the repository); on a Mac `python3 -m pip install openpyxl`. Stop until it passes.
- Check you can start helper agents (the Agent tool). If you cannot, a Quick check can still be done story by story by you, following `reference/briefs/extractor.md` for each story; a Full review is not possible. Say so and offer the Quick check.

## Step 2: Scan, then ask
Run the scan (safe to repeat; ids stay attached to the same files):
```bash
<py> "<skill-dir>/scripts/prepare_workdir.py" --source "<stories folder>" --label "<short name>"
```
It builds `<out>/_working` (scripts, config, briefs, codebook, record template) and scans the stories. Read `<work>/scan_report.txt` and tell the user in plain words: how many stories, the languages, files skipped and why (old `.doc`, PDF, a legacy Hindi font, duplicates, an earlier review folder), reused-text groups, notes per story. If the scan found no stories, say what it found and stop.

Then show the size: `<py> "<work>/scripts/estimate.py" --stories <N> --depth full` (and `--depth quick`).

Ask, in one go (AskUserQuestion; four questions at most):
1. **Depth.** Quick check (records, 19 Key Questions, readiness, consent register, writer questions; no second reader, no findings) or Full review (adds second reader, batch rulings, written findings tested by three skeptics). Recommend Quick for a first look or more than 30 stories.
2. **Translations.** If any story is English: are the English stories translations of stories written in another language? (`--translated yes`, `no`, or leave `auto`.)
3. **Settings.** Standard, or edit first (see Settings below).
4. **Leave out.** Any file or folder to exclude (`--exclude <text in the path>`).

For 30 or more stories: warn about size and offer a sample or a Quick check. For 60 or more: ask for a clear yes. Offer a **3-story pilot**: two independent extractors code the same three stories into `anchors/A` and `anchors/B`, then `<py> "<work>/scripts/agreement.py" anchors/A anchors/B`. Below about 80 percent agreement on Key Question statuses, say so and offer to continue anyway.

Then run prepare_workdir again with the answers (it re-renders the codebook for the depth):
```bash
<py> "<skill-dir>/scripts/prepare_workdir.py" --source "<stories folder>" --out "<out>" --depth <full|quick> --translated <yes|no|auto> --label "<name>" [--exclude "<text>" ...] [--settings "<workbook>"]
```
Keep `<py>` and `<work>` for the rest of the run.

## Step 3: Extract
Read `<work>/briefs/extractor.md` once so you know what the agents will do. Start one extractor agent for each story (three to five stories for each agent above 16 stories), at most 8 running at once. Prompt for each:
> You are an extractor for a story review. Working folder (read and write only inside it): `<work>`. Python command: `<py>`. Read `<work>/briefs/extractor.md` and follow it exactly. Your story ids: S03.

When they finish run `<py> "<work>/scripts/status.py"`. A record that fails the gate goes back to its agent (SendMessage) or to a new extractor with the gate's output; up to 3 tries. If more than a fifth still fail, stop and ask the user. If the session cannot run agents side by side, run them one after another and say it will be slow.

## Step 4 (Full only): Second read and batch rulings
- Verifiers: one agent for each pair of stories, prompt as above with `<work>/briefs/verifier.md`. Each writes `patches/<ID>.json` and checks it with `preview_patch.py`.
- `<py> "<work>/scripts/apply_patches.py"` writes `verify/` (stories with no patch are copied unchanged).
- `<py> "<work>/scripts/consistency_scan.py"`, then one harmoniser agent (`briefs/harmoniser.md`) writes `rulings.json` and checks it with `apply_rulings.py --dry-run`.
- Apply: `<py> "<work>/scripts/apply_rulings.py"`. If it reports problems, send them to the harmoniser. Tell the user how many rulings and changes there were; the codebook is not changed by rulings (suggestions are in `rulings.json` for a maintainer).

## Step 5: Compute (scripts only)
```bash
<py> "<work>/scripts/derive.py"          # derived flags, Key Question roll-ups, consent tiers; runs the gate again
<py> "<work>/scripts/aggregates.py"
<py> "<work>/scripts/text_checks.py"
<py> "<work>/scripts/readiness.py"
```
`derive.py` exits with an error if a final record fails the gate: stop, fix, repeat. Readiness bands come from a fixed rule. Override one only when the user asks and gives a reason, by writing `<work>/readiness_overrides.json`: `[{"story_id": "S02", "band": 2, "reason": "one sentence"}]`.

## Step 6 (Full only): Findings
1. Two analyst agents in parallel (`briefs/analyst.md`): lens set `structure` and lens set `meaning`; give each the review date (today). They write `claims/claims_structure.json` and `claims/claims_meaning.json`, checked with `claims_check.py`.
2. Merge and check: `<py> "<work>/scripts/claims_check.py" --merge claims/claims_structure.json claims/claims_meaning.json --out "<work>/claims/claims.json"`, then `claims_check.py claims/claims.json`. A finding that fails goes back to its analyst once; otherwise drop it.
3. `<py> "<work>/scripts/claim_pack.py" claims/claims.json`.
4. Three skeptic agents in parallel: `briefs/skeptic_evidence.md` (works blind), `skeptic_confounds.md`, `skeptic_fairness.md`. They write `skeptics/evidence.json`, `confounds.json`, `fairness.json`.
5. `<py> "<work>/scripts/apply_sceptics.py"` applies the survival rule.
6. One editor agent (`briefs/editor.md`) writes `claims/claims_final.json` and runs `finalize_claims.py` until it passes. A contested finding is dropped unless the editor writes a decision.

## Step 7: Build and check
```bash
<py> "<work>/scripts/build_readings.py"
<py> "<work>/scripts/build_workbook.py"
<py> "<work>/scripts/build_report.py"
<py> "<work>/scripts/verify_outputs.py"
<py> "<work>/scripts/run_log.py"
```
`verify_outputs.py` must pass every check. If one fails, say which and fix its cause (never loosen the check). Then `run_log.py`.

## Step 8: Deliver
Tell the user, in plain words and in this order:
1. What the batch shows: three to five sentences from the "In brief" section of the report (numbers exactly as the report has them).
2. Stories that need a consent check before any outside use (ids and tiers only, never why).
3. What needs a person's look from `RUN_LOG.md`: readiness overrides, contested or dropped findings, gate warnings, anything skipped.
4. The files and where they are: report, workbook, readings, log. Tell them the report and workbook are for the MEL team only and that `_working/` holds names and story texts and must not be shared.
5. The limits: counts describe these stories, not the programme; a Quick check has no findings; readiness measures the write-up.
6. What next: upgrade a Quick check to Full (see below), or change settings and re-run.
Do not paste a sensitive detail, a quote tied to a sensitive detail, or a ranking.

## Upgrade Quick to Full
Keep the records. Run prepare_workdir with `--depth full`, then start extractor agents with the word UPGRADE in the prompt (see `briefs/extractor.md`), and continue from Step 4.

## Settings the team can change
`<py> "<skill-dir>/scripts/settings_io.py" export "<stories folder>/story-review-settings.xlsx"` writes a workbook. The team can reword the 19 Key Questions, switch one off, add focus words, and reword the readiness tests and bands; nothing else. Re-run prepare_workdir with `--settings <file>` (it also finds `story-review-settings.xlsx` in the stories folder or its parent). The import refuses a bad row and says which. Every change is in the log and the report. If `batch.json`'s `questions_hash` changed after records exist, offer a targeted re-read of the changed questions.

## Resume
Any time: `<py> "<work>/scripts/status.py"` says what exists and what to do next.

## Unattended runs
Ask nothing. Use Quick, standard settings, `--translated auto`, no exclusions. Stop and say so if there are more than 60 stories or the check fails.

## If something goes wrong
- A script prints an error: show it in plain words and stop that stage.
- A story is skipped: the scan says why; relay it.
- The gate keeps failing for a story: ask the user whether to leave that story out (`--exclude`) and carry on.
- Never retry with a permission or sandbox bypass. Tell the user what is blocked.
