#!/usr/bin/env bash
# One-command launcher for Mac/Linux: sets up a virtual environment,
# installs dependencies, and starts the PDF Organizer.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required but was not found. Install it from https://python.org and try again."
  exit 1
fi

if [ ! -d .venv ]; then
  echo "Setting up (first run only)..."
  python3 -m venv .venv
fi

./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt

echo ""
echo "PDF Organizer is starting at http://localhost:8080"
echo "Press Ctrl+C to stop. Your work auto-saves."
echo ""
exec ./.venv/bin/python app.py
