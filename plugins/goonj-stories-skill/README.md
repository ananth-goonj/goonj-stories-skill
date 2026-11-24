# Goonj story review

A Claude plugin for the MEL team. Point it at a folder of field stories and it reviews them the same way every time:

- reads each story (Hindi, English or both) and records what it says, with the story's own words as proof;
- checks that every quote in a record is really in the story, by script;
- shows how well the stories answer the **19 Key Questions** (clear, partial or not stated), rolled up to What, Why, Who, Where, When and How;
- scores how ready each story is for outside use (a 12-test checklist and a band from 1 to 5);
- lists the stories that need a consent check before any outside use, without saying why;
- writes ranked questions for each writer;
- in a **Full** review, adds a second reader, batch rulings, and written findings that three independent skeptics have tested.

Everything stays on your computer. The report loads nothing from the web.

## What you get
In a new folder next to the stories (`Story Review <date>`):

| file | for |
|---|---|
| `... - Analysis Report.html` | the MEL team (internal only); opens in any browser |
| `... - Method and Data.xlsx` | the numbers, the exact words, the findings, the corrections log |
| `... - Story-by-Story Readings.md` | a reading of each story and the questions for its writer |
| `RUN_LOG.md` | what was done and what needs a person's look |

`reference/outputs.md` explains how to read each one.

## Install (one time)
1. You need **Claude on a paid plan that allows plugins** (Pro, Max, Team or Enterprise).
2. Install what the scripts need: **Python 3.9 or newer** and the **openpyxl** library. On Windows, double-click `install-requirements.bat` (it is at the top of the repository and inside this plugin folder). On a Mac, see `REQUIREMENTS.md`. The full list is in `REQUIREMENTS.md`.
3. In the Claude desktop app open **Customize**, then the **Plugins** tab, choose **Add from a repository**, paste `https://github.com/ananth-goonj/goonj-stories-skill` and install **goonj-stories-skill**. From the command line:

```bash
claude plugin marketplace add ananth-goonj/goonj-stories-skill
claude plugin install goonj-stories-skill@goonj-stories
```
If the repository is private you must be signed in to GitHub with access to it.

## Use it
Start Claude in the folder that holds your stories folder, then type:

```
/goonj-stories-skill:story-review
```
or ask in plain words: "Review the stories in my Stories folder". Claude asks which folder holds the stories, checks the computer, scans the files and shows what it found, then asks:

- Quick check or Full review? (Quick: records, Key Questions, readiness, consent, writer questions. Full adds the second reader, batch rulings, findings and skeptics.)
- Are the English stories translations?
- Standard settings, or edit them first?
- Anything to leave out?

For more than 30 stories it warns about size, and for more than 60 it asks you to confirm. A 3-story pilot is offered first.

## Settings you can change
The wording of each Key Question and whether it is used, the focus words searched in every story, and the wording of the readiness tests and bands. Ask Claude for the settings workbook, edit it in Excel, and name it when Claude asks. New questions and new tags need a developer, so numbers stay comparable between batches. Every change is listed in the log.

## Privacy rules built in
- Names tied to a health, injury, bereavement or menstrual detail are withheld in every output.
- The consent register shows how personal a detail is and where it sits, never what it is, story by story.
- No output ranks writers, or scores a story by how many questions it answers.
- Never commit stories, generated reports, a completed settings workbook, or the `_working` folder. The `.gitignore` here blocks them.

## If something goes wrong
- **"NOT READY" at the start:** run `install-requirements.bat` (Windows) or follow `REQUIREMENTS.md`, then ask again.
- **A story is skipped:** the scan lists it with the reason (old `.doc` format, a PDF, a legacy Hindi font). Save it as `.docx` or ask for a Unicode copy.
- **The run stopped half-way:** ask Claude to continue; it reads what exists and carries on from the next stage.
- **A name or detail looks wrong in the outputs:** do not share them; tell the maintainer, and run the review again after the records are fixed.

## For maintainers
`MAINTAINERS.md` says how to test, update and release this plugin. `reference/method.md` describes the method; `reference/pitfalls.md` lists traps from earlier reviews. Run `python3 tests/run_all.py` before every release.

---

## उपयोग कैसे करें (संक्षेप में)
1. Claude का paid plan चाहिए (Pro, Max, Team या Enterprise)। Windows पर `install-requirements.bat` चलाएँ; यह Python और openpyxl लगा देता है।
2. Claude डेस्कटॉप ऐप में **Customize → Plugins → Add from a repository** से यह प्लगइन जोड़ें।
3. Claude को कहानियों वाले फ़ोल्डर के ऊपर वाले फ़ोल्डर में खोलें और लिखें: `/goonj-stories-skill:story-review`।
4. Claude पूछेगा कि कहानियाँ किस फ़ोल्डर में हैं, फिर Quick या Full जाँच चुनने को कहेगा। नतीजे (रिपोर्ट, Excel और हर कहानी का पाठ) उसी जगह एक नए फ़ोल्डर में बनेंगे।
