#!/usr/bin/env bash
# macOS: double-click to run the desktop app from source.
# First run creates a local .venv and installs the dependencies.
cd "$(dirname "$0")"

pick_python() {
  for c in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys, tkinter; sys.exit(0 if sys.version_info >= (3, 10) else 1)' 2>/dev/null; then
      echo "$c"; return 0
    fi
  done
  return 1
}

if [ ! -x .venv/bin/python ]; then
  echo "First-time setup - this only happens once, please wait..."
  if PY="$(pick_python)"; then
    "$PY" -m venv .venv
  elif command -v uv >/dev/null 2>&1; then
    uv venv --python 3.12 .venv
  else
    echo
    echo " ========================================================="
    echo "  Python 3.10 or newer is not installed on this Mac."
    echo "  (macOS ships Python 3.9, which is too old.)"
    echo
    echo "  1. Go to https://www.python.org/downloads/macos/"
    echo "  2. Download and run the macOS installer."
    echo "  3. Double-click this file again."
    echo " ========================================================="
    read -r -p "Press Enter to close..." _
    exit 1
  fi
  .venv/bin/python -m ensurepip --upgrade >/dev/null 2>&1 || true
  .venv/bin/python -m pip install --quiet --upgrade pip
  .venv/bin/python -m pip install --quiet -r requirements.txt
fi

# Launch detached so this Terminal window can close.
nohup .venv/bin/python gui.py >/dev/null 2>&1 &
disown
osascript -e 'tell application "Terminal" to close (every window whose name contains "Run_App.command")' >/dev/null 2>&1 &
exit 0
