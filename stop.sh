#!/usr/bin/env bash
# Sauber alle Theatermaschine-Prozesse stoppen (Director-Ausgaben, Docker, natives Backend).
#
# Vom Projektroot:
#   ./stop.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

API="${THEATERMASCHINE_API:-http://localhost:8000/api/v1}"

post_quiet() {
  curl -sf -X POST "$1" -H "Content-Type: application/json" ${2:+-d "$2"} >/dev/null 2>&1
}

stop_director_outputs() {
  if ! curl -sf "${API%/api/v1}/docs" >/dev/null 2>&1; then
    return 0
  fi
  post_quiet "$API/director/emergency-stop" && echo "  Director: Emergency Stop"
  post_quiet "$API/director/technik/stop" '{}' && echo "  Technik-Hold: gestoppt"
  post_quiet "$API/director/light/stop" '{}' && echo "  Licht-Hold: gestoppt"
}

stop_port() {
  local port=$1
  local label=$2
  local pids
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return 0
  fi
  echo "  $label (Port $port): beende Prozess(e) $pids"
  # shellcheck disable=SC2086
  kill $pids 2>/dev/null || true
  sleep 0.4
  pids="$(lsof -ti:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    # shellcheck disable=SC2086
    kill -9 $pids 2>/dev/null || true
  fi
}

stop_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "  Docker: nicht installiert — übersprungen"
    return 0
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "  Docker: Daemon nicht erreichbar — übersprungen"
    return 0
  fi

  local native_file="$ROOT/docker-compose.native.yml"
  local base_file="$ROOT/docker-compose.yml"
  local running=""

  if [[ -f "$base_file" ]]; then
    if [[ -f "$native_file" ]]; then
      running="$(docker compose -f "$base_file" -f "$native_file" ps -q 2>/dev/null || true)"
      if [[ -n "$running" ]]; then
        echo "  Docker: compose down (mit native.yml)"
        docker compose -f "$base_file" -f "$native_file" down --remove-orphans
        return 0
      fi
    fi
    running="$(docker compose -f "$base_file" ps -q 2>/dev/null || true)"
    if [[ -n "$running" ]]; then
      echo "  Docker: compose down"
      docker compose -f "$base_file" down --remove-orphans
      return 0
    fi
  fi
  echo "  Docker: keine laufenden Compose-Services"
}

echo "=== Theatermaschine stoppen ==="
stop_director_outputs
stop_port 8000 "Backend (uvicorn)"
stop_port 3004 "Frontend (Host-Port)"
stop_docker
echo "Fertig."
