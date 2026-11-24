# Maintaining the story review plugin

## Install (for the team)
```bash
claude plugin marketplace add ananth-goonj/goonj-stories-skill
claude plugin install goonj-stories-skill@goonj-stories
```
Or in the Claude desktop app: **Customize**, then **Plugins**, then **Add from a repository**, and paste `https://github.com/ananth-goonj/goonj-stories-skill`. If the repository is private, each person must be signed in to GitHub with access to it. They start Claude in the folder that holds the stories folder and type `/goonj-stories-skill:story-review`.

## Before every release
```bash
python3 plugins/goonj-stories-skill/tests/run_all.py
```
It checks that every script parses, that no text file is opened without UTF-8, that the Windows installer is plain ASCII with Windows line endings, that no story, spreadsheet, place name or dataset name has crept in, and it replays the whole review on a made-up example (twice, the second time under a Windows-like setting). Every check must pass.

To also scan for writer, speaker, village, block and district names from earlier reviews, point `STORY_REVIEW_REAL_DATA` at the folders that hold them (separate several with the path separator). The names are read at run time and never stored in the plugin.

## Releasing a change
1. Edit the plugin in `plugins/goonj-stories-skill/`.
2. Run the checks above.
3. Raise `version` in `plugins/goonj-stories-skill/.claude-plugin/plugin.json`.
4. Commit and push. Ask people to run `claude plugin marketplace update goonj-stories`.

A change to the codebook or to the wording of a Key Question changes what answers mean. Tell people to re-read a batch before comparing it with an older one (the batch file records the question-set version).

## Never commit
Stories, generated reports, a completed settings workbook, or a `_working` folder. The `.gitignore` files in this repository block them; read `git status` before each commit.

## Not yet tested
- `install-requirements.bat` has not been run on Windows. It installs Python and the openpyxl library only; it does not install Claude.
- The report has been checked by script, not looked at in a browser on every screen size.
- Every agent role (extractor, second reader, harmoniser, analyst, the three skeptics, editor) has been run for real on one small batch of eight stories. A larger batch has not been run end to end.

## Putting it in the shared goonj-skills marketplace as well
Copy the plugin folder into that repository's `plugins/` folder and add the object in `marketplace-entry.json` to its `plugins` list. The marketplaces are named differently (`goonj-skills` and `goonj-stories`), so they do not clash.
