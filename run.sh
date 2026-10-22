#!/usr/bin/env bash
# One-command launcher: creates a virtualenv on first run, installs deps, runs the wizard if needed.
#   ./run.sh            → keep running (schedule + Telegram commands)
#   ./run.sh now        → one post now        ./run.sh preview → theme previews
set -euo pipefail
cd "$(dirname "$0")"
PY=${PYTHON:-python3}
if [ ! -d .venv ]; then
  echo "→ Creating virtual environment (.venv)…"
  "$PY" -m venv .venv
fi
VPY=.venv/bin/python
if [ ! -f .venv/.deps-ok ] || [ requirements.txt -nt .venv/.deps-ok ]; then
  echo "→ Installing dependencies…"
  "$VPY" -m pip install -q --upgrade pip
  "$VPY" -m pip install -q -r requirements.txt
  touch .venv/.deps-ok
fi
# first run: start the wizard (unless the user is already asking for it)
if [ ! -f .env ] && [ "${1:-}" != "setup" ]; then
  "$VPY" setup.py
fi
if [ $# -eq 0 ]; then set -- run; fi
exec "$VPY" bot.py "$@"
