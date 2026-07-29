#!/usr/bin/env bash
# Startet AutoPlay (make run) und öffnet das Frontend im Browser.
# Wird vom Desktop-App-Launcher aufgerufen.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND_URL="${AUTOPLAY_URL:-http://localhost:3004}"
SCRIPT_READY_URL="${AUTOPLAY_READY_URL:-http://localhost:3004/api/v1/productions}"
OPEN_URL="${AUTOPLAY_OPEN_URL:-http://localhost:3004/productions}"

cd "$ROOT"

ensure_docker() {
  if docker info >/dev/null 2>&1; then
    return 0
  fi
  echo "Docker ist nicht erreichbar — starte Docker Desktop…"
  open -a Docker || {
    echo "Docker Desktop konnte nicht gestartet werden." >&2
    echo "Bitte Docker manuell starten und erneut klicken." >&2
    exit 1
  }
  local i=0
  while ! docker info >/dev/null 2>&1; do
    i=$((i + 1))
    if [[ $i -ge 60 ]]; then
      echo "Timeout: Docker startet nicht (60s)." >&2
      exit 1
    fi
    sleep 2
  done
  echo "Docker ist bereit."
}

wait_and_open_browser() {
  local i=0
  echo "Warte auf Frontend…"
  while true; do
    if curl -sf "$SCRIPT_READY_URL" >/dev/null 2>&1; then
      open "$OPEN_URL"
      echo "AutoPlay geöffnet: $OPEN_URL"
      return 0
    fi
    i=$((i + 1))
    if [[ $i -ge 120 ]]; then
      echo "Frontend noch nicht erreichbar — öffne trotzdem: $OPEN_URL" >&2
      open "$OPEN_URL"
      return 0
    fi
    sleep 2
  done
}

echo "=== AutoPlay starten ==="
echo "Projekt: $ROOT"
ensure_docker

wait_and_open_browser &
OPENER_PID=$!

cleanup() {
  kill "$OPENER_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo ""
echo "Logs bleiben in diesem Fenster. Stoppen: Ctrl+C oder Desktop-Icon „AutoPlay Stop“."
echo ""

make run
