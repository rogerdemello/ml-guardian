#!/usr/bin/env bash
# ML Guardian - one command runs backend + frontend (macOS / Linux).
# Creates a venv, installs deps, opens the dashboard, and serves everything at :8000.
set -euo pipefail
PORT=8000

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

# Open the dashboard once the server is up.
( sleep 3; (command -v open >/dev/null && open "http://localhost:$PORT") || (command -v xdg-open >/dev/null && xdg-open "http://localhost:$PORT") || true ) &

echo ""
echo "ML Guardian running at http://localhost:$PORT  (Ctrl+C to stop)"
echo ""
exec ./.venv/bin/python -m uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT"
