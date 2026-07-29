#!/usr/bin/env bash
# Startet Theatermaschine (make run) und öffnet das Frontend im Browser.
# Wird vom Desktop-App-Launcher aufgerufen.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
FRONTEND_URL="${THEATERMASCHINE_URL:-http://localhost:3004}"
# Teil-2-Vorlage: erst öffnen, wenn Frontend + natives Backend die Kanon-Vorlage liefern
SCRIPT_READY_URL="${THEATERMASCHINE_SCRIPT_URL:-http://localhost:3004/api/v1/inszenierung/script}"
OPEN_URL="${THEATERMASCHINE_OPEN_URL:-http://localhost:3004/inszenierung}"

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
  echo "Warte auf Frontend + Kanon-Vorlage (Teil 2)…"
  while true; do
    # Proxy-Pfad prüft Frontend und Backend inkl. Stücktext-Vorlage
    if curl -sf "$SCRIPT_READY_URL" >/dev/null 2>&1; then
      open "$OPEN_URL"
      echo "Inszenierung geöffnet: $OPEN_URL"
      return 0
    fi
    i=$((i + 1))
    if [[ $i -ge 120 ]]; then
      echo "Vorlage noch nicht erreichbar — öffne trotzdem: $OPEN_URL" >&2
      open "$OPEN_URL"
      return 0
    fi
    sleep 2
  done
}

echo "=== Theatermaschine starten ==="
echo "Projekt: $ROOT"
ensure_docker

# Browser öffnen, sobald Frontend antwortet (parallel zu make run)
wait_and_open_browser &
OPENER_PID=$!

cleanup() {
  kill "$OPENER_PID" 2>/dev/null || true
}
trap cleanup EXIT

echo ""
echo "Logs bleiben in diesem Fenster. Stoppen: Ctrl+C oder Desktop-Icon „Theatermaschine Stop“."
echo ""

make run
