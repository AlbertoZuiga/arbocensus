#!/usr/bin/env bash
set -euo pipefail

# Convenience script to create venv, install deps and run the app
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# Load .env if present (check subproject first, then repo root)
if [ -f "$ROOT_DIR/.env" ]; then
  # export variables from .env for the process
  set -a
  . "$ROOT_DIR/.env"
  set +a
elif [ -f "$ROOT_DIR/../.env" ]; then
  set -a
  . "$ROOT_DIR/../.env"
  set +a
fi

source .venv/bin/activate
pip install -r requirements.txt
python app.py
