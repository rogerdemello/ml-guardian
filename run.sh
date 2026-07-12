#!/usr/bin/env bash
# ML Guardian - one-command local launcher (macOS / Linux)
# Creates a venv, installs deps, and starts the app at http://localhost:8000
set -euo pipefail

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv .venv
fi

echo "Installing dependencies..."
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "Created .env from .env.example (offline fixture mode, no keys required)."
fi

echo "Starting ML Guardian at http://localhost:8000 ..."
./.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
