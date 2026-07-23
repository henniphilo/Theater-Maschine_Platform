#!/usr/bin/env bash
# Backend nativ auf dem Mac (MIDI → Ableton, macOS say-TTS).
#
# Voraussetzung (im Projektroot):
#   docker compose -f docker-compose.yml -f docker-compose.native.yml up -d postgres redis frontend
#   docker compose stop backend
#
# Ohne docker-compose.native.yml ist Postgres nur intern im Container — localhost:5432 schlägt fehl.

set -euo pipefail
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"

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

# host.docker.internal gilt nur im Docker-Container — nativ für Legacy-OSC (TouchDesigner)
export OSC_HOST="${OSC_HOST:-127.0.0.1}"
# PIXERA_OSC_* aus backend/.env — hier nicht überschreiben (z. B. 172.27.27.1:8990)

# Nativ auf dem Mac: Siri-Stimmen (say) — nicht edge-tts
export TTS_PROVIDER="${TTS_PROVIDER:-say}"

# Repo-Daten/Logs (nicht backend/data — dort liegt nur ggf. lokales tts/)
export DIRECTOR_DATA_DIR="${DIRECTOR_DATA_DIR:-$ROOT/data}"
export STORAGE_ROOT="${STORAGE_ROOT:-$ROOT/storage}"
export OSC_LOG_PATH="${OSC_LOG_PATH:-$ROOT/logs/osc.log}"
export DIRECTOR_LOG_PATH="${DIRECTOR_LOG_PATH:-$ROOT/logs/director.log}"
export SIGNAL_TRACE_PATH="${SIGNAL_TRACE_PATH:-$ROOT/logs/signal_trace.jsonl}"

_db_host="${DATABASE_URL:-}"
if [[ "$_db_host" == *"@localhost:"* ]] || [[ -z "$_db_host" ]]; then
  if ! python - <<'PY'
import socket
s = socket.socket()
s.settimeout(1)
try:
    s.connect(("127.0.0.1", 5432))
except OSError:
    raise SystemExit(1)
finally:
    s.close()
PY
  then
    echo "PostgreSQL auf localhost:5432 nicht erreichbar." >&2
    echo "" >&2
    echo "Postgres/Redis mit Port-Mapping starten (Projektroot):" >&2
    echo "  cd \"$ROOT\"" >&2
    echo "  docker compose -f docker-compose.yml -f docker-compose.native.yml up -d postgres redis frontend" >&2
    echo "  docker compose stop backend" >&2
    echo "" >&2
    echo "Falls Postgres schon ohne Port-Mapping läuft, einmal neu anlegen:" >&2
    echo "  docker compose -f docker-compose.yml -f docker-compose.native.yml up -d --force-recreate postgres" >&2
    exit 1
  fi
fi

python -m app.db.init_db

UVICORN_ARGS=(app.main:app --reload --port 8000 --log-level "${APP_LOG_LEVEL:-warning}")
if [[ "${UVICORN_ACCESS_LOG:-false}" != "true" ]]; then
  UVICORN_ARGS+=(--no-access-log)
fi

exec uvicorn "${UVICORN_ARGS[@]}"
