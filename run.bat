@echo off
REM One-command launcher for Windows.
REM   run.bat            -> keep running (schedule + Telegram commands)
REM   run.bat now        -> one post now        run.bat preview -> theme previews
setlocal
cd /d "%~dp0"
if not exist .venv (
  echo Creating virtual environment...
  py -3 -m venv .venv 2>nul || python -m venv .venv
)
set VPY=.venv\Scripts\python.exe
if not exist .venv\.deps-ok (
  echo Installing dependencies...
  %VPY% -m pip install -q --upgrade pip
  %VPY% -m pip install -q -r requirements.txt && type nul > .venv\.deps-ok
)
if not exist .env if /i not "%~1"=="setup" %VPY% setup.py
if "%~1"=="" (%VPY% bot.py run) else (%VPY% bot.py %*)
endlocal
