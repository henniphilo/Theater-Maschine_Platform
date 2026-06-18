#!/usr/bin/env bash
# Backend nativ auf dem Mac (MIDI → Ableton, macOS say-TTS).
# Voraussetzung:
#   docker compose -f docker-compose.yml -f docker-compose.native.yml up -d postgres redis frontend
#   docker compose stop backend

set -euo pipefail
cd "$(dirname "$0")"

if ! command -v python3.11 >/dev/null 2>&1; then
  echo "python3.11 fehlt. Installieren: brew install python@3.11" >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  python3.11 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

if ! python -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "Alte .venv mit Python < 3.11 — neu anlegen mit: rm -rf .venv && ./run-native.sh" >&2
  exit 1
fi

pip install -q --upgrade pip
pip install -q -e .

# host.docker.internal gilt nur im Docker-Container — nativ localhost
export OSC_HOST="${OSC_HOST:-127.0.0.1}"
export PIXERA_OSC_HOST="${PIXERA_OSC_HOST:-127.0.0.1}"

python -m app.db.init_db
exec uvicorn app.main:app --reload --port 8000
