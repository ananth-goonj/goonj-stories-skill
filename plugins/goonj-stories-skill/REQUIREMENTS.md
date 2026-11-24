# What you need to run the story review

The skill runs inside Claude. Claude runs a few small scripts on your computer, so these things must be there.

## Required

| what | why | how to get it |
|---|---|---|
| **Claude, on a paid plan that allows plugins** (Pro, Max, Team or Enterprise), in the Claude desktop app | the skill is a Claude plugin | Install the Claude desktop app, then **Customize > Plugins > Add from a repository** (see the README). The free plan has no plugins. |
| **Python 3.9 or newer** | the scripts that read the stories, check the records, count and build the files | Windows: run `install-requirements.bat`. Mac: see below. |
| **The Python library openpyxl** | it writes the Excel workbook | Windows: `install-requirements.bat` does it. Everywhere else: `python3 -m pip install openpyxl` |

That is the whole list for running the review. Nothing else is installed on your computer by the skill.

## Needed to read the results (you probably have them)
- A web browser, to open the report (it works offline and on a phone).
- Excel, or any spreadsheet program, to open the workbook.
- A Word processor, to read the `.docx` stories you start from.

## Not needed
LibreOffice, Git (to use the skill), Node, extra fonts, and any internet connection other than the one Claude itself uses. The scripts make no web requests and the report loads nothing from the web.

## Windows
Double-click **`install-requirements.bat`**. It installs Python and openpyxl for you (it needs Windows 10 or 11 with the Windows Package Manager, called winget, which is already there on most computers). It does not install Claude. When it finishes it says what to do next. If your work computer does not let you install programs, ask your IT team to install Python 3.9 or newer and then run `py -m pip install openpyxl`.

## Mac
1. Open Terminal and type `python3 --version`. If it prints 3.9 or newer, go to step 3.
2. If Python is missing, type `xcode-select --install` and follow the prompts, or install Python from python.org.
3. Type `python3 -m pip install openpyxl`.

## Linux
Install Python 3.9 or newer with your package manager (for example `sudo apt install python3 python3-pip`), then `python3 -m pip install openpyxl`.

## Check that you are ready
Ask Claude to start the review: the first thing it does is a check and it tells you what is missing. Or run it yourself, from the plugin folder:

```bash
python3 skills/story-review/scripts/preflight.py
```
(On Windows use `py` instead of `python3`.) It prints READY or says exactly what to install.

## What Claude needs permission to do
Run Python scripts in the working folder, read the folder that holds the stories, and write the review into a new folder next to them. For a Full review it also starts helper agents. It never changes your story files.

## Time and cost
A Quick check of a few stories takes minutes; a Full review of a large folder takes hours and uses a lot of Claude capacity. Claude shows an estimate and asks before it starts anything large.
