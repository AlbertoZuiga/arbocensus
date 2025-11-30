#!/usr/bin/env bash
set -euo pipefail

# run.sh - convenience script
# Default: run with Docker Compose (development mode)
# Use `./run.sh --local` or `./run.sh local` or `./run.sh -l` to run in a local venv

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

show_help() {
  cat <<EOF
Usage: ./run.sh [--local|-l|local] [COMMAND]

Default (no flags): builds and runs with Docker Compose (docker compose up --build).
Local mode: creates/uses .venv, loads .env and runs the app with the local Python interpreter.

COMMAND (optional): passed to Docker Compose when running in docker mode.
Examples:
  ./run.sh                      # docker compose up --build
  ./run.sh -d                   # docker compose up --build -d
  ./run.sh --local              # run locally in .venv
  ./run.sh local                # same as --local
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  show_help
  exit 0
fi

LOCAL=0
case "${1:-}" in
  -l|--local|local)
    LOCAL=1
    # shift past mode arg
    shift || true
    ;;
esac

if [ "$LOCAL" -eq 0 ]; then
  # Docker Compose mode (default)
  # Pass any remaining args to docker compose (e.g., -d)
  DOCKER_ARGS=("up" "--build")
  if [ "$#" -gt 0 ]; then
    DOCKER_ARGS=("up" "--build" "$@")
  fi

  echo "Starting with Docker Compose: docker compose ${DOCKER_ARGS[*]}"
  # Ensure .env is not baked into image; docker-compose will load it via env_file
  docker compose "${DOCKER_ARGS[@]}"
  exit $?
fi

# Local mode: create/use .venv, load .env and run app.py
if [ ! -d ".venv" ]; then
  echo "Creating virtualenv .venv..."
  python3 -m venv .venv
fi

# Load .env if present (check subproject first, then repo root)
if [ -f "$ROOT_DIR/.env" ]; then
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

echo "Running app locally (python app.py)"
python app.py
