@echo off
setlocal EnableExtensions
title Goonj story review - install requirements

rem Installs what the story review skill needs on Windows: Python 3.9 or newer, and the openpyxl library.
rem It does NOT install Claude. You need Claude (a paid plan that allows plugins) separately.
rem It changes nothing else on this computer. A log is written to the TEMP folder.

set "LOG=%TEMP%\goonj-story-review-install.log"
echo Goonj story review: install requirements> "%LOG%"
echo.
echo ================================================================
echo  Goonj story review - install requirements
echo ================================================================
echo.
echo This installs Python (3.9 or newer) and the openpyxl library.
echo It does not install Claude. You need Claude on a paid plan
echo that allows plugins, set up separately.
echo.

set "PYCMD="

rem ---- 1. is a usable Python already here?
call :try_py "py -3"
if not defined PYCMD call :try_py "python"
if not defined PYCMD call :try_py "python3"
if defined PYCMD goto :have_python

echo Python 3.9 or newer was not found on this computer.
echo.
where winget >nul 2>&1
if errorlevel 1 goto :no_winget

rem ---- 2. install Python for the current user with winget
echo Installing Python 3.12 with the Windows Package Manager (winget).
echo This can take a few minutes. If Windows asks for permission, choose Yes.
echo.
winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements >> "%LOG%" 2>&1
set "WGERR=%errorlevel%"

rem The new Python is not on PATH in this window yet, so look in the usual folder.
set "NEWPY=%LocalAppData%\Programs\Python\Python312\python.exe"
if exist "%NEWPY%" call :try_exe "%NEWPY%"
if not defined PYCMD call :try_py "py -3"
if defined PYCMD goto :have_python
if not "%WGERR%"=="0" goto :winget_failed
goto :not_found_after_install

:have_python
echo Found Python: %PYCMD%
%PYCMD% --version
echo.
echo Installing the openpyxl library (it writes the Excel workbook)...
%PYCMD% -m pip install --upgrade openpyxl >> "%LOG%" 2>&1
if errorlevel 1 goto :pip_failed
%PYCMD% -c "import openpyxl, sys; print('openpyxl', openpyxl.__version__, 'is installed; Python', sys.version.split()[0])"
if errorlevel 1 goto :pip_failed

echo.
echo ================================================================
echo  ALL DONE. This computer has what the story review needs.
echo ================================================================
echo.
echo Next:
echo   1. Open the Claude desktop app.
echo   2. Start Claude in the folder that holds your stories folder.
echo   3. Type:  /goonj-stories-skill:story-review
echo.
echo If Claude says something is missing, run this file again.
goto :end

:try_py
%~1 -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 3)" >nul 2>&1
if not errorlevel 1 set "PYCMD=%~1"
goto :eof

:try_exe
"%~1" -c "import sys; sys.exit(0 if sys.version_info>=(3,9) else 3)" >nul 2>&1
if not errorlevel 1 set PYCMD="%~1"
goto :eof

:no_winget
echo The Windows Package Manager (winget) is not available here, so Python
echo cannot be installed automatically. Please install it by hand:
echo   1. Open https://www.python.org/downloads/ and download Python 3.12 for Windows.
echo   2. Run the installer, tick "Add python.exe to PATH", then choose Install Now.
echo   3. Run this file again.
echo If this is a work computer that does not allow installs, ask your IT team
echo to install Python 3.9 or newer, and then run this file again.
goto :failed

:winget_failed
echo Winget could not install Python. The details are in this file:
echo   %LOG%
echo Please install Python by hand (python.org, "Add python.exe to PATH"),
echo or ask your IT team, then run this file again.
goto :failed

:not_found_after_install
echo Python was installed, but this window cannot find it yet.
echo Close this window, open this file again, and it will carry on.
goto :failed

:pip_failed
echo The openpyxl library could not be installed. The details are in this file:
echo   %LOG%
echo You can try by hand in a new window:   py -m pip install openpyxl
echo If you are not connected to the internet, connect and run this file again.
goto :failed

:failed
echo.
echo NOT FINISHED. Nothing else on this computer was changed.
echo.
pause
exit /b 1

:end
echo.
pause
exit /b 0
