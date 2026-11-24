# Goonj story review

A Claude plugin for the MEL team. Point it at a folder of field stories and it reviews them the same way every time: it records what each story says with the story's own words as proof, checks every quote by script, shows how well the stories answer the 19 Key Questions, scores readiness for outside use, lists the stories that need a consent check, and writes ranked questions for each writer. A Full review adds a second reader, batch rulings and written findings tested by three independent skeptics.

Everything stays on your computer. The report loads nothing from the web.

## What you need
- **Claude on a paid plan that allows plugins** (Pro, Max, Team or Enterprise).
- **Python 3.9 or newer** and the **openpyxl** library. On Windows, double-click `install-requirements.bat` in this folder: it installs both (it does not install Claude). On a Mac or Linux see `plugins/goonj-stories-skill/REQUIREMENTS.md`.

## Install (one time)
In the Claude desktop app open **Customize**, then the **Plugins** tab, choose **Add from a repository**, paste `https://github.com/ananth-goonj/goonj-stories-skill` and install **goonj-stories-skill**. From the command line:

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
Claude asks which folder holds the stories, checks the computer, scans the files, and asks whether you want a Quick check or a Full review.

## More
- `plugins/goonj-stories-skill/README.md`: what you get, the settings you can change, the privacy rules built in, and what to do when something goes wrong.
- `plugins/goonj-stories-skill/MAINTAINERS.md`: how to test, update and release the plugin.
- Never commit stories, generated reports, a completed settings workbook or a `_working` folder. The `.gitignore` here blocks them.
